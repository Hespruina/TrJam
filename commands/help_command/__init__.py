# commands/help_command/__init__.py
# 重构后的帮助命令，从命令分发器中独立出来

import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from utils.task_utils import create_monitored_task
from commands.help_command.help_sender import process_help_request

logger = get_logger("HelpCommand")

async def handle_help_command(context: BotContext, **kwargs) -> CommandResponse:
    """处理help命令：直接生成并发送帮助信息。"""
    # 从kwargs中获取参数
    user_id = kwargs.get('user_id')
    group_id = kwargs.get('group_id')
    server_name = kwargs.get('server_name')
    group_id_str = str(group_id) if group_id else None
    sender_role = kwargs.get('sender_role')
    
    # 检查是否为已配置群聊
    is_configured = False
    if server_name and context.config.get("servers", {}).get(server_name, {}).get("groups", {}).get(group_id_str):
        is_configured = True
    
    # 发送处理中提示
    processing_builder = MessageBuilder(context)
    processing_builder.set_group_id(group_id)
    processing_builder.set_user_id(user_id)
    processing_builder.add_at()
    processing_builder.add_text("📚 正在为您准备帮助信息，请稍候...")
    
    async def processing_callback(message_id: str):
        if message_id:
            # 启动后台任务处理帮助请求，并传递处理中消息的ID
            create_monitored_task(
                process_help_request(context, user_id, group_id, server_name, group_id_str, message_id, sender_role),
                name=f"HelpCommand_process_{user_id}_{group_id}"
            )
    
    processing_builder.set_callback(processing_callback)
    
    # 发送处理中提示
    await processing_builder.send()
    
    # 返回none表示已经通过builder发送了消息
    return CommandResponse.none()
