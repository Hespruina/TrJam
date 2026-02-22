# commands/softmute_command.py
# 处理 /softmute mute/unmute 命令 - 软禁言功能

import json
import os
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_utils import parse_at_or_qq

logger = get_logger("SoftmuteCommand")

def get_softmute_file_path(group_id: str) -> str:
    """获取软禁言配置文件路径"""
    return f"data/softmute/{group_id}.json"

def load_softmute_data(group_id: str) -> dict:
    """加载软禁言数据"""
    softmute_file = get_softmute_file_path(group_id)
    try:
        if os.path.exists(softmute_file):
            with open(softmute_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"加载软禁言数据失败: {e}")
    return {"muted_users": {}}

def save_softmute_data(group_id: str, data: dict):
    """保存软禁言数据"""
    softmute_file = get_softmute_file_path(group_id)
    try:
        directory = os.path.dirname(softmute_file)
        os.makedirs(directory, exist_ok=True)
        with open(softmute_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"软禁言数据已保存至: {softmute_file}")
    except Exception as e:
        logger.error(f"保存软禁言数据失败: {e}")
        raise

def is_user_softmuted(group_id: str, user_id: str) -> bool:
    """检查用户是否被软禁言"""
    data = load_softmute_data(group_id)
    return str(user_id) in data.get("muted_users", {})

async def handle_softmute_command(context: BotContext, args: list, user_id: str, group_id: str, command: str, sender_role: str = None, **kwargs) -> str:
    """处理 /softmute mute/unmute 命令"""
    from commands.permission_manager import check_permission
    
    user_level = check_permission(context, user_id, group_id, sender_role)
    
    if user_level < 1:
        return "❌ 只有管理员才能使用软禁言命令"
    
    if not args:
        return "❌ 参数错误，格式：/softmute [mute/unmute] @用户或QQ号"
    
    action = None
    target_user_id = None
    
    if args[0].lower() in ["mute", "unmute"]:
        action = args[0].lower()
        if len(args) < 2:
            return "❌ 请指定要操作的用户（@用户或QQ号）"
        target_user_id, _ = parse_at_or_qq(args[1:])
    else:
        target_user_id, _ = parse_at_or_qq(args)
        if not target_user_id:
            return "❌ 无效的 QQ 号或 @ 格式"
        
        data = load_softmute_data(group_id)
        muted_users = data.get("muted_users", {})
        
        if str(target_user_id) in muted_users:
            action = "unmute"
        else:
            action = "mute"
    
    if not target_user_id:
        return "❌ 无效的 QQ 号或 @ 格式"
    
    if target_user_id == str(user_id):
        return "⚠️ 你不能软禁言自己"
    
    if target_user_id == str(context.get_config_value("bot_qq", "")):
        return "⚠️ 你不能软禁言机器人"
    
    if target_user_id == str(context.get_config_value("Root_user", "")):
        return "⚠️ 你不能软禁言Root用户"
    
    data = load_softmute_data(group_id)
    muted_users = data.get("muted_users", {})
    
    if action == "mute":
        if str(target_user_id) in muted_users:
            return f"⚠️ 用户 {target_user_id} 已经在软禁言列表中"
        
        muted_users[str(target_user_id)] = {
            "operator": str(user_id),
            "timestamp": int(__import__('time').time())
        }
        data["muted_users"] = muted_users
        save_softmute_data(group_id, data)
        
        logger.info(f"用户 {user_id} 在群 {group_id} 软禁言了用户 {target_user_id}")
        return f"✅ 已将用户 {target_user_id} 添加到软禁言列表"
    
    elif action == "unmute":
        if str(target_user_id) not in muted_users:
            return f"⚠️ 用户 {target_user_id} 不在软禁言列表中"
        
        del muted_users[str(target_user_id)]
        data["muted_users"] = muted_users
        save_softmute_data(group_id, data)
        
        logger.info(f"用户 {user_id} 在群 {group_id} 解除了用户 {target_user_id} 的软禁言")
        return f"✅ 已将用户 {target_user_id} 从软禁言列表移除"
    
    return "❌ 未知错误"
