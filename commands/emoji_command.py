# 处理 '/emoji' 命令

from logger_config import get_logger
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.message_sender import MessageBuilder, CommandResponse
from utils.task_utils import create_monitored_task
from .permission_manager import check_permission
import asyncio
import time
import random

logger = get_logger("EmojiCommand")

# 存储用户最后一次执行emoji命令的时间戳
# {user_id: last_execution_time}
emoji_cooldowns = {}

async def handle_emoji_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """处理 '/emoji' 命令，给指定消息添加表情回应。"""
    try:
        # 获取原始消息内容以检查是否有引用消息
        raw_message = kwargs.get('raw_message', [])
        
        # 尝试从引用消息中获取消息ID
        message_id = None
        if isinstance(raw_message, list):
            for segment in raw_message:
                if segment.get('type') == 'reply':
                    message_id = segment.get('data', {}).get('id')
                    break
        
        # 如果没有引用消息，检查参数
        if not message_id:
            if len(args) < 1:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❌ 请引用一条消息或提供消息ID")
                await builder.send()
                return CommandResponse.none()
            message_id = args[0]
        
        # 检查权限级别
        user_level = check_permission(context, user_id, group_id)
        
        # 检查冷却时间（5秒）
        current_time = time.time()
        if user_level < 2:  # 只有Root用户没有冷却时间
            last_time = emoji_cooldowns.get(user_id, 0)
            cooldown_time = 20  # 5秒冷却时间
            if current_time - last_time < cooldown_time:
                remaining_time = int(cooldown_time - (current_time - last_time))
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text(f"⏱️ 表情回应功能冷却中，请等待 {remaining_time} 秒后再试~")
                await builder.send()
                return CommandResponse.none()
        
        # 解析emoji使用次数
        times = 1  # 默认1次
        if len(args) > 0 and args[-1].isdigit():
            times = int(args[-1])
            # 检查次数限制
            if user_level < 2:  # Root用户无次数限制
                if user_level < 1 and times > 5:  # 普通用户限制5次
                    builder = MessageBuilder(context)
                    builder.set_group_id(group_id)
                    builder.set_user_id(user_id)
                    builder.add_at()
                    builder.add_text("⚠️ 普通用户最多只能使用5次表情回应哦~")
                    await builder.send()
                    return CommandResponse.none()
                elif user_level == 1 and times > 10:  # 管理员限制12次
                    builder = MessageBuilder(context)
                    builder.set_group_id(group_id)
                    builder.set_user_id(user_id)
                    builder.add_at()
                    builder.add_text("⚠️ 管理员最多只能使用10次表情回应哦~")
                    await builder.send()
                    return CommandResponse.none()
            elif times <= 0:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❌ 表情回应次数必须大于0！")
                await builder.send()
                return CommandResponse.none()
        
        logger.info(f"用户 {user_id} 在群 {group_id} 执行了 emoji 命令，消息ID: {message_id}，次数: {times}")
        
        # 更新冷却时间（非Root用户）
        if user_level < 2:
            emoji_cooldowns[user_id] = time.time()
        
        # 创建后台任务处理耗时的表情回应操作
        create_monitored_task(
            process_emoji_request(context, user_id, group_id, message_id, times),
            name=f"EmojiCommand_process_{user_id}_{group_id}_{message_id}"
        )
        
        # 返回none表示已经通过builder发送了消息
        return CommandResponse.none()
        
    except Exception as e:
        logger.error(f"处理emoji命令时发生异常: {e}", exc_info=True)
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("❌ 表情回应失败，请稍后再试~")
        await builder.send()
        return CommandResponse.none()

async def process_emoji_request(context: BotContext, user_id: str, group_id: str, message_id: str, times: int):
    """在后台处理表情回应请求的耗时操作"""
    try:
        # 使用call_onebot_api发送表情回应
        success_count = 0
        for i in range(times):
            try:
                # 生成随机emoji_id (1-231)
                emoji_id = random.randint(1, 231)
                
                # 并行调用set_msg_emoji_like API，同时添加和移除表情
                response_true, response_false = await asyncio.gather(
                    call_onebot_api(
                        context=context,
                        action="set_msg_emoji_like",
                        params={
                            "message_id": message_id,
                            "emoji_id": emoji_id,
                            "set": True
                        }
                    ),
                    call_onebot_api(
                        context=context,
                        action="set_msg_emoji_like",
                        params={
                            "message_id": message_id,
                            "emoji_id": emoji_id,
                            "set": False
                        }
                    )
                )
                
                # 检查API调用结果
                if response_true and response_true.get('success'):
                    logger.info(f"已在群 {group_id} 第 {i+1}/{times} 次为消息 {message_id} 添加表情回应(true)，emoji_id: {emoji_id}")
                    
                    if response_false and response_false.get('success'):
                        logger.info(f"已在群 {group_id} 第 {i+1}/{times} 次为消息 {message_id} 移除表情回应(false)，emoji_id: {emoji_id}")
                        success_count += 1
                    else:
                        logger.warning(f"在群 {group_id} 第 {i+1}/{times} 次为消息 {message_id} 移除表情回应失败: {response_false}")
                else:
                    logger.error(f"调用set_msg_emoji_like API失败: {response_true.get('error') if response_true else '无响应'}")
                
                # 在每次操作之间添加小延迟
                if i < times - 1:  # 不是最后一次操作
                    await asyncio.sleep(0.05)
                    
            except Exception as api_error:
                logger.error(f"调用set_msg_emoji_like API失败: {api_error}")
        
        # 发送结果消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        
        if success_count > 0:
            builder.add_text(f"✅ 已成功为消息 {message_id} 添加表情回应 {success_count}次~")
        else:
            builder.add_text("❌ 表情回应失败，请稍后再试~")
        
        await builder.send()
        
    except Exception as e:
        logger.error(f"处理表情回应请求时发生异常: {e}", exc_info=True)
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("❌ 表情回应过程中发生错误，请稍后再试~")
        await builder.send()