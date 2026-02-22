# commands/command_dispatcher/command_authorizer.py
# 负责权限检查

from logger_config import get_logger
from core.bot_context import BotContext
# 导入信任管理器
from core.trust_manager import trust_manager
from utils.message_sender import MessageBuilder

logger = get_logger("CommandAuthorizer")

async def check_authorization(context: BotContext, command: str, group_id: str, user_id: str, nickname: str) -> bool:
    """检查命令授权"""
    from commands.bancommand_command import is_command_banned
    
    # 检查命令是否被禁用
    if is_command_banned(context, command, group_id):
        logger.debug(f"命令 '{command}' 已被禁用，不返回任何提示")
        return False

    # 检查是否为中文命令
    from commands.command_dispatcher.command_registry import CHINESE_COMMAND_MAPPING
    if command in CHINESE_COMMAND_MAPPING:
        english_command = CHINESE_COMMAND_MAPPING[command]
        logger.debug(f"检测到中文命令 '{command}'，映射到英文命令 '{english_command}'")
        # 使用英文命令名查找处理器
        command = english_command

    # 查找命令配置
    cmd_config = context.config["commands"].get(command, {
        "permission": "User",
        "description": "",
        "usage": ""
    })

    # 检查命令是否需要信任群组
    need_trust = cmd_config.get("need_trust", False)
    if need_trust and not trust_manager.is_trusted_group(str(group_id)):
        # 群组不在信任列表中，发送提示消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" 当前群未被信任，无法使用该功能。请联系ROOT用户了解如何信任本群。Root用户QQ：2711631445")
        await builder.send()
        return False
    
    return True

async def check_permission(context: BotContext, user_id: str, group_id: str, sender_role: str) -> int:
    """检查用户权限。"""
    from commands.permission_manager import check_permission
    return check_permission(context, user_id, group_id, sender_role or "member")