# handlers/group_handler/message_processor.py
# 群组消息处理模块

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

logger = get_logger("GroupMessageProcessor")

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
        from handlers.group_handler.sensitive_message_handler import handle_sensitive_message
        await handle_sensitive_message(context, event, group_id, user_id, original_message, sensitive_word, sensitive_reason)
        return # 敏感消息已被处理，不再继续
    elif contains_sensitive and not sensitive_word_recall_enabled:
        # 敏感词功能未启用，仅记录日志并发送报告
        log_sensitive_trigger(original_message, sensitive_word, group_id, user_id)
        logger.debug(f"已记录敏感词触发日志，但未启用自动撤回功能")
        from handlers.group_handler.sensitive_message_handler import send_sensitive_report
        await send_sensitive_report(context, group_id, user_id, original_message, sensitive_word)

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
        from handlers.group_handler.auto_mute_handler import handle_auto_mute
        await handle_auto_mute(context, user_id, nickname, group_id)
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
    from handlers.group_handler.image_handler import handle_image_messages
    await handle_image_messages(context, event, group_id, user_id, nickname)
    
    # 处理群聊防刷屏功能
    # from handlers.group_handler.antiswipe_handler import handle_antiswipe_detection
    # await handle_antiswipe_detection(context, event, group_id, user_id, original_message)

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