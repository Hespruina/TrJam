# commands/group_command/blacklist_handler.py
# 黑名单处理功能

import json
import os
import re
from utils.message_sender import CommandResponse
from logger_config import get_logger

logger = get_logger("GroupCommandBlacklist")

async def handle_blacklist_command(context, args, user_id, group_id, user_level, sender_role=None):
    """处理 /group blacklist 子命令"""
    # 检查权限，群主、管理员及以上权限可以使用
    has_permission = user_level >= 1 or sender_role in ["admin", "owner"]
    if not has_permission:
        return CommandResponse.text("❌ 权限不足，需要管理员权限")
    
    if len(args) < 1:
        return CommandResponse.text("用法: /group blacklist add/rm [QQ号或@用户]\n或: /group blacklist list")
    
    blacklist_action = args[0].lower()
    
    if blacklist_action == "list":
        return await list_blacklist(context, group_id)
    elif blacklist_action == "add":
        if len(args) < 2:
            return CommandResponse.text("用法: /group blacklist add [QQ号或@用户]")
        return await add_to_blacklist(context, args[1], user_id, group_id)
    elif blacklist_action == "rm":
        if len(args) < 2:
            return CommandResponse.text("用法: /group blacklist rm [QQ号或@用户]")
        return await remove_from_blacklist(context, args[1], user_id, group_id)
    else:
        return CommandResponse.text("❌ 无效的操作，支持的操作: add, rm, list")

async def list_blacklist(context, group_id):
    """列出所有黑名单用户"""
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
            return CommandResponse.text("❌ 读取群组配置文件失败")
    
    # 检查是否存在blacklist
    if "blacklist" not in group_config or not group_config["blacklist"]:
        return CommandResponse.text("📋 当前黑名单为空")
    
    # 构建黑名单列表
    blacklist = group_config["blacklist"]
    blacklist_list = ["📋 群黑名单列表:"]
    for i, blacklisted_user in enumerate(blacklist):
        blacklist_list.append(f"{i+1}. {blacklisted_user}")
    
    return CommandResponse.text("\n".join(blacklist_list))

async def add_to_blacklist(context, target_user, user_id, group_id):
    """添加用户到黑名单"""
    # 解析目标用户QQ号
    target_user_id = _parse_user_id(target_user)
    if not target_user_id:
        return CommandResponse.text("❌ 无效的QQ号或@用户格式")
    
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
            return CommandResponse.text("❌ 读取群组配置文件失败")
    
    # 确保 blacklist 字段存在
    if "blacklist" not in group_config:
        group_config["blacklist"] = []
    
    # 检查用户是否已在黑名单中
    if target_user_id in group_config["blacklist"]:
        return CommandResponse.text(f"❌ 用户 {target_user_id} 已在黑名单中")
    
    # 添加到黑名单列表
    group_config["blacklist"].append(target_user_id)
    
    # 保存配置
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(group_config_path), exist_ok=True)
        
        with open(group_config_path, 'w', encoding='utf-8') as f:
            json.dump(group_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群组配置文件失败: {e}")
        return CommandResponse.text("❌ 保存群组配置文件失败")
    
    return CommandResponse.text(f"✅ 已将用户 {target_user_id} 添加到黑名单")

async def remove_from_blacklist(context, target_user, user_id, group_id):
    """从黑名单中移除用户"""
    # 解析目标用户QQ号
    target_user_id = _parse_user_id(target_user)
    if not target_user_id:
        return CommandResponse.text("❌ 无效的QQ号或@用户格式")
    
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
            return CommandResponse.text("❌ 读取群组配置文件失败")
    
    # 检查是否存在blacklist
    if "blacklist" not in group_config or not group_config["blacklist"]:
        return CommandResponse.text("❌ 当前黑名单为空")
    
    # 检查用户是否在黑名单中
    if target_user_id not in group_config["blacklist"]:
        return CommandResponse.text(f"❌ 用户 {target_user_id} 不在黑名单中")
    
    # 从黑名单中移除
    group_config["blacklist"].remove(target_user_id)
    
    # 保存配置
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(group_config_path), exist_ok=True)
        
        with open(group_config_path, 'w', encoding='utf-8') as f:
            json.dump(group_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群组配置文件失败: {e}")
        return CommandResponse.text("❌ 保存群组配置文件失败")
    
    return CommandResponse.text(f"✅ 已将用户 {target_user_id} 从黑名单中移除")

def _parse_user_id(user_input):
    """解析用户输入，提取QQ号"""
    # 处理@用户格式
    at_pattern = r'\[CQ:at,qq=(\d+)\]'
    match = re.search(at_pattern, user_input)
    if match:
        return match.group(1)
    
    # 处理直接输入QQ号格式
    if user_input.isdigit():
        return user_input
    
    return None