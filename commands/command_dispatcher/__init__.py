# commands/command_dispatcher/__init__.py
# 负责将命令分发给具体的命令处理器

from logger_config import get_logger
from core.bot_context import BotContext
from typing import Optional

logger = get_logger("CommandDispatcher")

async def dispatch_command(context: BotContext, message: str, user_id: str, group_id: str, nickname: str, **kwargs) -> Optional[str]:
    """命令分发器，根据命令名调用对应的处理器。"""
    # 检查用户是否在黑名单中
    from commands.command_dispatcher.command_registry import _is_user_blacklisted
    if await _is_user_blacklisted(context, group_id, user_id):
        logger.info(f"用户 {user_id} 在群 {group_id} 的黑名单中，忽略其命令")
        return None

    # 检查授权
    from commands.command_dispatcher.command_authorizer import check_authorization
    raw_command = message.strip().split()[0] if message.strip().split() else ""
    command = raw_command.lstrip('/')
    if not await check_authorization(context, command, group_id, user_id, nickname):
        return None

    # 执行命令
    from commands.command_dispatcher.command_executor import execute_command
    return await execute_command(context, message, user_id, group_id, nickname, **kwargs)

# 导出命令处理器映射（register_command装饰器已移除）
from commands.command_dispatcher.command_registry import initialize_command_mappings, COMMAND_HANDLERS, CHINESE_COMMAND_MAPPING, GLOBAL_COMMANDS, ENGLISH_COMMAND_MAPPING