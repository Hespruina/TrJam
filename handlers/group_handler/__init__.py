# handlers/group_handler/__init__.py
# 群组消息处理模块

from handlers.group_handler.message_processor import handle_group_message

__all__ = ['handle_group_message']

import json
import time
import asyncio
import uuid
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.message_sender import MessageBuilder
from utils.task_utils import create_monitored_task
# 导入信任管理器
from core.trust_manager import trust_manager
# 导入消息处理工具
from utils.message_utils import parse_message, is_traditional_chinese, convert_to_simplified
# 从敏感词管理器导入需要的函数
from core.sensitive_word_manager import is_sensitive, log_sensitive_trigger
# 导入命令分发器
from commands.command_dispatcher import dispatch_command
# 导入OpenCC
from opencc import OpenCC
# 导入图片处理相关函数
from utils.vision_utils import download_image_async, image_to_base64_async, is_leg_photo_async

logger = get_logger("GroupHandler")

async def handle_group_message(context: BotContext, event: dict):
    """处理群聊消息事件。"""
    # 检查是否应该处理该消息（基于当前活跃账号）
    if not context.should_handle_message(event):
        return
        
    group_id = event.get('group_id', '')
    group_id_str = str(group_id)
    user_id = str(event.get('user_id', ''))
    raw_message = event.get('message', '')
    original_message = parse_message(raw_message).strip()
    
    # 保留原始消息的大小写，只在命令匹配时进行小写转换
    message_for_command_matching = original_message
    
    sender = event.get('sender', {})
    nickname = sender.get('card') or sender.get('nickname', '未知用户')
    # 获取用户角色
    sender_role = sender.get('role')

    logger.debug(f"群 {group_id} 中用户 {user_id} ({nickname}) 发送消息: {original_message}")

    # 检查用户是否在黑名单中
    if await _is_user_blacklisted(context, group_id_str, user_id):
        logger.info(f"用户 {user_id} 在群 {group_id} 的黑名单中，忽略其消息")
        return

    # 检查消息是否在黑名单中（完全匹配）
    blacklist_msg = context.get_config_value('blacklist_msg', [])
    if blacklist_msg and original_message in blacklist_msg:
        logger.info(f"消息 '{original_message}' 在黑名单中，不进行处理，群: {group_id}，用户: {user_id}")
        return

    # 获取群组配置
    group_config = context.get_group_config(group_id_str)
    # 保留group_config用于toggle功能控制的命令

    # 繁体字检测与转换
    simplified_text = None
    if is_traditional_chinese(original_message):
        # 检查群组是否在信任列表中，使用字符串类型确保类型一致
        if trust_manager.is_trusted_group(group_id_str):
            # 过滤掉CQ码，只对纯文本进行繁简转换
            filtered_text = re.sub(r'\[CQ:[^\]]*\]', '', original_message).strip()
            if filtered_text:  # 确保过滤后还有文本内容
                simplified_text = convert_to_simplified(filtered_text)
        else:
            logger.info(f"群 {group_id} 不在信任列表中，不进行繁体转换")

    # 如果是繁体字且非敏感，发送转换结果
    if simplified_text:
        logger.info(f"发送繁体转换结果到群: {group_id}")
        # 构建消息内容
        message_content = [
            {"type": "text", "data": {"text": f"繁体转换：{simplified_text}"}}
        ]
        
        # 使用BotContext中的send_group_message方法发送消息
        async def simplified_message_sent_callback(message_id):
            logger.debug(f"已发送繁体转换结果到群: {group_id}，消息ID: {message_id}")
        
        if context.websocket and not context.websocket.closed:
            # 使用MessageBuilder构建并发送消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.add_text(f"繁体转换：{simplified_text}")
            builder.set_callback(simplified_message_sent_callback)
            await builder.send()

    # 敏感词检测
    text_to_check = simplified_text or original_message
    contains_sensitive, sensitive_word, sensitive_reason = is_sensitive(text_to_check)

    # 检查是否启用了敏感词自动撤回功能
    # 使用toggle功能控制的配置
    sensitive_word_recall_enabled = group_config.get('sensitive_word_recall_enabled', False) if group_config else False
    
    if contains_sensitive and sensitive_word_recall_enabled:
        await _handle_sensitive_message(context, event, group_id, user_id, original_message, sensitive_word, sensitive_reason)
        return # 敏感消息已被处理，不再继续
    elif contains_sensitive and not sensitive_word_recall_enabled:
        # 敏感词功能未启用，仅记录日志并发送报告
        log_sensitive_trigger(original_message, sensitive_word, group_id, user_id)
        logger.debug(f"已记录敏感词触发日志，但未启用自动撤回功能")
        await _send_sensitive_report(context, group_id, user_id, original_message, sensitive_word)

    # 过滤机器人自己的消息
    bot_qq = str(context.get_config_value("bot_qq", ""))
    if user_id == bot_qq:
        logger.debug(f"检测到来自机器人自身在群聊中发送: {original_message}")
        if message_for_command_matching.startswith('/') or message_for_command_matching in ['赞我']:
            logger.info(f"检测到消息为指令，正在执行: {original_message}")
            bot_nickname = "Bot"
            result = await dispatch_command(context, original_message, user_id, group_id, bot_nickname, raw_message=raw_message, websocket=context.websocket)
            if result is not None:
                # 构建消息内容
                message_content = [
                    {"type": "at", "data": {"qq": user_id}},
                    {"type": "text", "data": {"text": f"{result}"}}
                ]
                
                # 使用BotContext中的send_group_message方法发送消息
                async def bot_message_sent_callback(message_id):
                    logger.info(f"已将指令 '{original_message}' 的执行结果发送到 QQ 群 {group_id}，消息ID: {message_id}")
                
                if context.websocket and not context.websocket.closed:
                    # 使用MessageBuilder构建并发送消息
                    builder = MessageBuilder(context)
                    builder.set_group_id(group_id)
                    builder.add_at(user_id)
                    builder.add_text(f"{result}")
                    builder.set_callback(bot_message_sent_callback)
                    await builder.send()
        else:
            logger.debug("该消息不是指令。")
        return

    # 处理主动禁言
    auto_mute_commands = ['禁言我', '禁我', '塞我口球']
    if message_for_command_matching in [cmd.lower() for cmd in auto_mute_commands]:
        # 如果群组或用户在黑名单中，则发送警告而不是执行禁言（已经提前检查过了）
        await _handle_auto_mute(context, user_id, nickname, group_id)
        return

    # 处理命令
    # 1. 检查是否以斜杠开头的命令
    is_valid_command = False
    if message_for_command_matching.startswith('/'):
        logger.info(f"收到斜杠命令: {original_message} 来自用户: {user_id} (群: {group_id})")
        is_valid_command = True
        try:
            # 处理命令（新版命令处理器会自己发送消息）
            message_id = event.get('message_id')
            await dispatch_command(context, original_message, user_id, group_id, nickname, 
                                 raw_message=raw_message, websocket=context.websocket, 
                                 message_id=message_id, sender_role=sender_role)
        except Exception as e:
            logger.error(f"处理命令 {original_message} 时发生异常: {e}", exc_info=True)
    # 2. 检查是否为无斜杠的中文命令
    else:
        # 获取消息的第一个词（假设命令是单个词）
        first_word = message_for_command_matching.strip().split()[0] if message_for_command_matching.strip() else ""
        
        # 导入command_dispatcher中的CHINESE_COMMAND_MAPPING来检查是否为中文命令
        from commands.command_dispatcher import CHINESE_COMMAND_MAPPING, GLOBAL_COMMANDS
        
        # 检查是否为已注册的中文命令（仅允许中文命令别名无斜杠触发）
        if first_word in CHINESE_COMMAND_MAPPING or first_word in ['赞我']:
            logger.info(f"收到无斜杠命令: {first_word} 来自用户: {user_id} (群: {group_id})")
            is_valid_command = True
            try:
                # 处理命令（新版命令处理器会自己发送消息）
                message_id = event.get('message_id')
                await dispatch_command(context, original_message, user_id, group_id, nickname, 
                                     raw_message=raw_message, websocket=context.websocket, 
                                     message_id=message_id, sender_role=sender_role)
            except Exception as e:
                logger.error(f"处理无斜杠命令 {first_word} 时发生异常: {e}", exc_info=True)
    
    # 处理图片并检查是否为腿照
    await handle_image_messages(context, event, group_id, user_id, nickname)

async def _is_user_blacklisted(context: BotContext, group_id: str, user_id: str) -> bool:
    """检查用户是否在群组黑名单中"""
    # 获取群组配置文件路径
    group_config_path = f"data/group_config/{group_id}.json"
    
    # 读取现有配置
    group_config = {}
    if os.path.exists(group_config_path):
        try:
            with open(group_config_path, 'r', encoding='utf-8') as f:
                group_config = json.load(f)
        except Exception as e:
            logger.error(f"读取群组配置文件失败: {e}")
            return False
    
    # 检查是否存在blacklist以及用户是否在其中
    if "blacklist" in group_config and user_id in group_config["blacklist"]:
        return True
    
    return False

async def process_image_for_leg_detection(context, event, group_id, user_id, nickname, image_urls):
    """在后台处理图片并识别腿照的协程函数"""
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    temp_dir = os.path.join(project_root, 'temp_images')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)

    try:
        for image_url in image_urls:
            save_path = os.path.join(temp_dir, f"temp_image_{uuid.uuid4()}.jpg")
            try:
                await download_image_async(image_url, save_path)
                # 转换为base64
                base64_image = await image_to_base64_async(save_path)
                
                # 识别是否为腿照
                if base64_image:
                    is_leg_photo = await is_leg_photo_async(context, base64_image)
                    if is_leg_photo and event.get('message_id'):
                        # 调用onebot API设置精华消息
                        essence_result = await call_onebot_api(
                            context, 'set_essence_msg', {'message_id': event.get('message_id')}
                        )
                        # 检查设置精华是否成功
                        if essence_result and essence_result.get('success') and essence_result.get('data', {}).get('status') == 'ok':
                            logger.info(f"成功将腿照设置为精华消息，群: {group_id}，用户: {user_id}({nickname})")
                            # 发送提示消息
                            builder = MessageBuilder(context)
                            builder.set_group_id(str(group_id))
                            builder.set_user_id(user_id)
                            builder.add_at()
                            builder.add_text(" 腿照已被设为精华！")
                            await builder.send()
                            break  # 找到一张腿照并设为精华后就可以退出了
                        else:
                            logger.error(f"设置精华消息失败，群: {group_id}，用户: {user_id}")
            except Exception as e:
                log_exception(logger, f"处理图片 {image_url} 时发生异常", e)
            finally:
                # 清理临时文件
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except Exception as e:
                        logger.error(f"删除临时文件失败: {save_path}", e)
    except Exception as e:
        log_exception(logger, "处理图片消息时发生异常", e)

async def handle_image_messages(context: BotContext, event: dict, group_id: str, user_id: str, nickname: str):
    """处理消息中的图片，识别腿照并设置精华"""
    # 检查是否启用了腿照自动设为精华功能
    # 使用toggle功能控制的配置
    group_config = context.get_group_config(str(group_id))
    leg_photo_enabled = group_config.get("leg_photo_essence_enabled", False) if group_config else False
    if not leg_photo_enabled:
        logger.debug(f"腿照自动设为精华功能未启用，群: {group_id}")
        return

    # 检查全局LLM开关
    if not context.get_config_value("llm_enabled", False):
        logger.debug("LLM功能已禁用，跳过腿照识别")
        return

    # 从消息中提取图片URL
    message = event.get('message', [])
    image_urls = extract_image_urls(message)
    
    # 如果没有图片，直接返回
    if not image_urls:
        return

    # 从配置获取最多处理的图片数量
    ai_vision_config = context.get_config_value("ai_vision", {})
    if ai_vision_config:
        leg_detection_config = ai_vision_config.get("leg_photo_detection", {})
        max_images = leg_detection_config.get("max_images_per_message", 3)
    else:
        max_images = 3
    
    # 限制处理的图片数量，避免API调用过多
    image_urls = image_urls[:max_images]

    logger.debug(f"检测到群 {group_id} 中用户 {user_id}({nickname}) 发送了 {len(image_urls)} 张图片，准备进行腿照识别")
    
    # 创建后台任务处理图片，避免阻塞WebSocket连接
    create_monitored_task(
        process_image_for_leg_detection(context, event, group_id, user_id, nickname, image_urls),
        f"LegPhotoDetection-{group_id}-{user_id}"
    )


def extract_image_urls(message):
    """从消息中提取图片URL"""
    image_urls = []
    if isinstance(message, list):
        for segment in message:
            if isinstance(segment, dict) and segment.get('type') == 'image':
                # 尝试获取URL，OneBot不同版本字段可能不同
                image_url = segment.get('data', {}).get('url')
                if not image_url:
                    image_url = segment.get('data', {}).get('file')
                if image_url:
                    image_urls.append(image_url)
    return image_urls

# 本地工具函数
def is_traditional_chinese(text):
    """检测文本是否包含繁体字。"""
    cc = OpenCC('t2s')
    converted = cc.convert(text)
    return text != converted

def convert_to_simplified(text):
    """将繁体字转换为简体字。"""
    cc = OpenCC('t2s')
    return cc.convert(text)

async def _send_sensitive_report(context: BotContext, group_id: str, user_id: str, message: str, sensitive_word: str, recalled: bool = False):
    """发送敏感词报告到配置的目标"""
    from utils.sensitive_word_reporter import SensitiveWordReporter
    try:
        success = await SensitiveWordReporter.send_report(
            context, group_id, user_id, message, sensitive_word, recalled
        )
        if not success:
            logger.warning("敏感词报告发送失败")
    except Exception as e:
        logger.error(f"发送敏感词报告时发生异常: {str(e)}")

async def _handle_sensitive_message(context: BotContext, event: dict, group_id, user_id, original_message, sensitive_word, sensitive_reason):
    """处理包含敏感词的消息。"""
    logger.info(f"检测到敏感词，群: {group_id}，用户: {user_id}，敏感词: {sensitive_word}，原因: {sensitive_reason}")
    # 使用管理器记录日志
    log_sensitive_trigger(original_message, sensitive_word, group_id, user_id)
    logger.debug(f"已记录敏感词触发日志")

    # 检查是否启用了敏感词自动撤回功能
    group_config = context.get_group_config(str(group_id))
    sensitive_word_recall_enabled = group_config.get("sensitive_word_recall_enabled", False) if group_config else False

    if not sensitive_word_recall_enabled:
        logger.debug(f"敏感词自动撤回功能未启用，群: {group_id}")
        return

    # 获取群组配置
    is_configured_group = group_config is not None

    if is_configured_group:
        try:
            message_id = event.get('message_id')
            if message_id:
                from utils.api_utils import call_onebot_api
                recall_result = await call_onebot_api(
                    context, 'delete_msg', {'message_id': message_id}
                )
                # 检查API调用是否成功以及业务处理是否成功
                if recall_result and recall_result.get('success') and recall_result.get('data', {}).get('status') == 'ok':
                    logger.info(f"已成功撤回敏感消息，群: {group_id}，用户: {user_id}")
                    # 构建消息并发送
                    builder = MessageBuilder(context)
                    builder.set_group_id(str(group_id))
                    builder.set_user_id(user_id)
                    builder.add_at()
                    builder.add_text(f" 含有{sensitive_reason}内容，已撤回")
                    # 启用敏感词绕过高阶，原因是系统通知
                    builder.set_badword_bypass(True, "系统敏感词通知", "system")
                    await builder.send()

                    # 推送报告到指定群（已撤回）
                    await _send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, True)
                else:
                    # 提供更详细的失败原因
                    failure_reason = "未知原因"
                    if recall_result:
                        if not recall_result.get('success'):
                            failure_reason = recall_result.get('error', 'API调用失败')
                        else:
                            failure_reason = f"业务状态非成功: {recall_result.get('data', {}).get('status', '未知')}"
                    logger.error(f"撤回敏感消息失败，群: {group_id}，用户: {user_id}，原因: {failure_reason}")
                    # 推送报告到指定群（未撤回）
                    await _send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, False)
            else:
                logger.error(f"无法获取消息ID，无法撤回敏感消息，群: {group_id}，用户: {user_id}")
                # 推送报告到指定群（未撤回）
                await _send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, False)
        except Exception as e:
            logger.error(f"处理敏感消息时发生异常: {e}")
            # 推送报告到指定群（处理异常，视为未撤回）
            await _send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, False)
    else:
        logger.info(f"未配置群聊中检测到敏感词，不执行撤回也不发送回复，群: {group_id}，用户: {user_id}")

async def _handle_auto_mute(context: BotContext, user_id: str, nickname: str, group_id: str):
    """处理用户主动请求禁言。"""
    logger.info(f"用户 {user_id}({nickname}) 请求主动禁言")
    try:
        mute_duration = 950400 + 14400 + 300 # 11天4小时5分钟
        from utils.api_utils import call_onebot_api
        mute_result = await call_onebot_api(
            context, 'set_group_ban',
            {
                'group_id': group_id,
                'user_id': user_id,
                'duration': mute_duration
            }
        )
        # 检查API调用是否成功以及业务处理是否成功
        if mute_result and mute_result.get('success') and mute_result.get('data', {}).get('status') == 'ok':
            logger.info(f"成功禁言用户 {user_id}({nickname})，时长：{mute_duration}秒")
            # 构建消息并发送
            builder = MessageBuilder(context)
            builder.set_group_id(str(group_id))
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(" 已为您禁言11天4小时5分钟捏")
            await builder.send()

            # 创建一个后台任务，在20秒后自动解禁
            async def auto_unmute_task():
                await asyncio.sleep(20)
                try:
                    unmute_result = await call_onebot_api(
                        context, 'set_group_ban',
                        {
                            'group_id': group_id,
                            'user_id': user_id,
                            'duration': 0
                        }
                    )
                    # 检查API调用是否成功以及业务处理是否成功
                    if unmute_result and unmute_result.get('success') and unmute_result.get('data', {}).get('status') == 'ok':
                        logger.info(f"成功取消用户 {user_id}({nickname}) 的禁言")
                    else:
                        logger.error(f"取消用户 {user_id}({nickname}) 禁言失败")
                except Exception as e:
                    logger.error(f"自动解禁用户时发生异常: {e}")

            # 使用create_monitored_task创建后台任务
            create_monitored_task(auto_unmute_task(), name=f"AutoUnmute_{user_id}_{group_id}")
        else:
            # 提供更详细的失败原因
            failure_reason = "未知原因"
            if mute_result:
                if not mute_result.get('success'):
                    failure_reason = mute_result.get('error', 'API调用失败')
                else:
                    failure_reason = f"业务状态非成功: {mute_result.get('data', {}).get('status', '未知')}"
            logger.error(f"禁言用户失败，群: {group_id}，用户: {user_id}，原因: {failure_reason}")
            # 发送失败消息
            builder = MessageBuilder(context)
            builder.set_group_id(str(group_id))
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f" 禁言失败：{failure_reason}")
            await builder.send()
    except Exception as e:
        logger.error(f"处理用户主动禁言时发生异常: {e}")
        # 发送异常消息
        builder = MessageBuilder(context)
        builder.set_group_id(str(group_id))
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" 禁言处理过程中发生异常，请联系管理员")
        await builder.send()

        # 使用MessageBuilder构建并发送欢迎消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(welcome_message)
        await builder.send()