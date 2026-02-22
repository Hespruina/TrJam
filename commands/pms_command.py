# commands/pms_command.py
# 处理 /pms 命令

from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_utils import parse_at_or_qq

logger = get_logger("PmsCommand")

async def handle_pms_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> str:
    """处理 /pms 命令，管理群管理员"""
    if len(args) < 1:
        return "❌ 参数错误，格式：/pms [add/remove/list] [@用户或QQ号]"

    action = args[0].lower()
    if action not in ["add", "remove", "list"]:
        return "❌ 无效操作，支持 add/remove/list"
    
    from commands.permission_manager import load_permissions, save_permissions
    permissions = load_permissions(context, group_id)
    
    if action == "list":
        if not permissions['Admin']:
            return "ℹ️ 当前没有设置管理员"
        
        # 获取用户昵称
        admin_list = []
        for admin_id in permissions['Admin']:
            from utils.user_utils import get_user_nickname
            nickname = await get_user_nickname(context, admin_id)
            admin_list.append(f"{nickname}({admin_id})" if nickname else admin_id)
        
        return f"🔑 当前管理员列表:\n" + "\n".join([f"  {i+1}. {admin}" for i, admin in enumerate(admin_list)])
    
    if len(args) < 2:
        return "❌ 参数错误，格式：/pms [add/remove] [@用户或QQ号]"
    
    # 使用parse_at_or_qq函数解析@用户或QQ号格式
    target, _ = parse_at_or_qq(args[1:])
    if not target:
        target = args[1]

    if action == "add":
        if target in permissions['Admin']:
            return "⚠️ 该用户已是管理员"
        permissions['Admin'].append(target)
        save_permissions(context, permissions, group_id)
        return f"✅ 已添加管理员: {target}"

    elif action == "remove":
        if target not in permissions['Admin']:
            return "⚠️ 该用户不是管理员"
        permissions['Admin'].remove(target)
        save_permissions(context, permissions, group_id)
        return f"✅ 已移除管理员: {target}"

    else:
        return "❌ 未知错误"