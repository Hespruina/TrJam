# commands/allquote_command.py
# 处理 /allquote 命令 - 句句名言功能

import json
import os
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_utils import parse_at_or_qq

logger = get_logger("AllquoteCommand")

def get_allquote_file_path(group_id: str) -> str:
    """获取句句名言配置文件路径"""
    return f"data/allquote/{group_id}.json"

def load_allquote_data(group_id: str) -> dict:
    """加载句句名言数据"""
    allquote_file = get_allquote_file_path(group_id)
    try:
        if os.path.exists(allquote_file):
            with open(allquote_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"加载句句名言数据失败: {e}")
    return {"quoted_users": {}}

def save_allquote_data(group_id: str, data: dict):
    """保存句句名言数据"""
    allquote_file = get_allquote_file_path(group_id)
    try:
        directory = os.path.dirname(allquote_file)
        os.makedirs(directory, exist_ok=True)
        with open(allquote_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"句句名言数据已保存至: {allquote_file}")
    except Exception as e:
        logger.error(f"保存句句名言数据失败: {e}")
        raise

def is_user_allquoted(group_id: str, user_id: str) -> bool:
    """检查用户是否在句句名言名单中"""
    data = load_allquote_data(group_id)
    return str(user_id) in data.get("quoted_users", {})

async def handle_allquote_command(context: BotContext, args: list, user_id: str, group_id: str, command: str, sender_role: str = None, **kwargs) -> str:
    """处理 /allquote 命令"""
    from commands.permission_manager import check_permission
    
    user_level = check_permission(context, user_id, group_id, sender_role)
    
    if user_level < 1:
        return "❌ 只有管理员才能使用句句名言命令"
    
    if not args:
        return "❌ 参数错误，格式：/allquote @用户或QQ号"
    
    target_user_id, _ = parse_at_or_qq(args)
    
    if not target_user_id:
        return "❌ 无效的 QQ 号或 @ 格式"
    

    
    data = load_allquote_data(group_id)
    quoted_users = data.get("quoted_users", {})
    
    if str(target_user_id) in quoted_users:
        del quoted_users[str(target_user_id)]
        data["quoted_users"] = quoted_users
        save_allquote_data(group_id, data)
        
        logger.info(f"用户 {user_id} 在群 {group_id} 解除了用户 {target_user_id} 的句句名言")
        return f"✅ 已将用户 {target_user_id} 从句句名言名单移除"
    else:
        quoted_users[str(target_user_id)] = {
            "operator": str(user_id),
            "timestamp": int(__import__('time').time())
        }
        data["quoted_users"] = quoted_users
        save_allquote_data(group_id, data)
        
        logger.info(f"用户 {user_id} 在群 {group_id} 为用户 {target_user_id} 添加了句句名言")
        return f"✅ 已将用户 {target_user_id} 添加到句句名言名单"
