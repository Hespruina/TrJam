# commands/group_command/__init__.py
# 处理 /group 命令，用于群组相关设置

from utils.message_sender import CommandResponse
from commands.group_command.blacklist_handler import handle_blacklist_command
from commands.group_command.join_handler import handle_join_command
# from commands.group_command.antiswipe_handler import handle_antiswipe_command

async def handle_group_command(context, args, user_id, group_id, user_level, sender_role=None, **kwargs):
    """处理 /group 命令，用于群组相关设置"""
    
    # 检查权限，群主、管理员及以上权限可以使用
    # user_level 0: User, 1: Admin, 2: Root
    # sender_role: "member", "admin", "owner"
    has_permission = user_level >= 1 or sender_role in ["admin", "owner"]
    if not has_permission:
        return CommandResponse.text("❌ 权限不足，需要管理员权限")
    
    if len(args) < 1:
        return CommandResponse.text("用法: /group join set [level/answer] [값]\n或: /group join list\n或: /group join rm [编号]\n或: /group join welcome [消息内容]\n或: /group blacklist add/rm [QQ号或@用户]\n或: /group blacklist list")
    
    subcommand = args[0].lower()
    
    # 处理 join 子命令（原 toggle event 功能）
    if subcommand == "join":
        return await handle_join_command(context, args[1:], user_id, group_id, user_level, sender_role)
    elif subcommand == "blacklist":
        return await handle_blacklist_command(context, args[1:], user_id, group_id, user_level, sender_role)
    # elif subcommand in ["antiswipe", "as"]:
    #     return handle_antiswipe_command(context, args[1:], user_id, group_id, user_level, sender_role)
    else:
        return CommandResponse.text("❌ 无效的子命令，支持的子命令: join, blacklist")

