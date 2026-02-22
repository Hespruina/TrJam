# commands/permission_manager.py
# 重构后的权限管理模块

import json
import os
from logger_config import get_logger, log_exception
from core.bot_context import BotContext

logger = get_logger("PermissionManager")

# 权限配置缓存，格式：{group_id: (permissions_dict, last_modified_time)}
_permission_cache = {}

# 缓存过期时间（秒）
_CACHE_EXPIRY = 300

def load_permissions(context: BotContext, group_id: str) -> dict:
    """加载指定群组的权限配置，带缓存机制"""
    group_id_str = str(group_id)
    permission_file = f"data/group_config/{group_id_str}.json"
    
    # 检查缓存是否存在且未过期
    current_time = os.path.getmtime(permission_file) if os.path.exists(permission_file) else 0
    if group_id_str in _permission_cache:
        cached_perms, cached_mtime = _permission_cache[group_id_str]
        if cached_mtime == current_time:
            logger.debug(f"从缓存加载群组 {group_id} 的权限配置")
            return cached_perms
    
    logger.debug(f"从文件加载群组 {group_id} 的权限配置: {permission_file}")
    
    try:
        with open(permission_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f"已从 {permission_file} 加载权限数据")
            # 更新缓存
            _permission_cache[group_id_str] = (data, current_time)
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"权限文件 {permission_file} 异常 ({type(e).__name__})，将创建默认文件")
        default = {"Root": [context.get_config_value("Root_user")], "Admin": []}
        save_permissions(context, default, group_id)
        # 更新缓存
        _permission_cache[group_id_str] = (default, current_time)
        return default

def save_permissions(context: BotContext, data: dict, group_id: str):
    """保存指定群组的权限配置，并更新缓存"""
    group_id_str = str(group_id)
    permission_file = f"data/group_config/{group_id_str}.json"
    logger.debug(f"为群组 {group_id} 使用默认权限文件用于保存: {permission_file}")

    try:
        directory = os.path.dirname(permission_file)
        os.makedirs(directory, exist_ok=True)
        with open(permission_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"权限文件已成功保存至: {permission_file}")
        
        # 更新缓存
        current_time = os.path.getmtime(permission_file)
        _permission_cache[group_id_str] = (data, current_time)
    except IOError as e:
        log_exception(logger, f"保存权限文件 {permission_file} 失败", e)
        raise

def check_permission(context: BotContext, user_id: str, group_id: str, sender_role: str = None) -> int:
    """检查用户权限级别。"""
    # 如果用户是Root用户，直接返回最高权限
    if str(user_id) == str(context.get_config_value("Root_user")):
        return 2
    
    # 如果用户是群主(owner)或管理员(admin)，默认拥有管理员权限
    if sender_role in ["owner", "admin"]:
        return 1
    
    # 检查配置文件中的权限设置
    permissions = load_permissions(context, group_id)
    if str(user_id) in permissions.get('Root', []):
        return 2
    if str(user_id) in permissions.get('Admin', []):
        return 1
    return 0

def clear_permission_cache(group_id: str = None):
    """清除权限缓存，可以指定群组ID"""
    if group_id:
        group_id_str = str(group_id)
        if group_id_str in _permission_cache:
            del _permission_cache[group_id_str]
            logger.debug(f"已清除群组 {group_id} 的权限缓存")
    else:
        _permission_cache.clear()
        logger.debug("已清除所有权限缓存")