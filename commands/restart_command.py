# commands/restart_command.py
# 处理 /restart 命令

import os
import sys
import time
import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender.message_builder import MessageBuilder

logger = get_logger("RestartCommand")

async def handle_restart_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> int:
    """处理 /restart 命令，重启机器人。
    
    Returns:
        int: 0 表示消息处理流程正常完成，1 表示消息处理过程中出现错误
    """
    try:
        # 检查是否为Root用户
        root_user_id = context.get_config_value("Root_user")
        if str(user_id) != str(root_user_id):
            # 使用MessageBuilder发送权限错误消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("⚠️ 该命令仅限Root用户使用")
            await builder.send()
            return 0
        
        # 使用MessageBuilder通知用户机器人将重启
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("🔄 机器人正在重启...")
        await builder.send()
        
        # 设置重启标志
        restart_flag = os.path.join(os.path.dirname(__file__), '..', '.restart_flag')
        with open(restart_flag, 'w') as f:
            f.write(str(time.time()))
        
        # 快速触发重启，不等待正常清理
        import bot
        bot._fast_exit = True
        
        # 返回0表示消息处理成功
        return 0
    except Exception as e:
        logger.error(f"重启机器人时发生异常: {e}")
        
        # 发送错误消息
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 重启失败")
        await error_builder.send()
        
        # 返回1表示消息处理过程中出现错误
        return 1