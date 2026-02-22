# 封禁命令模块

import json
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.message_sender import CommandResponse, MessageBuilder
from commands.permission_manager import load_permissions, save_permissions

logger = get_logger("BanCommand")

async def handle_bancommand_command(context: BotContext, **kwargs) -> CommandResponse:
    """处理封禁命令：添加或移除被禁用的命令。"""
    user_id = kwargs.get('user_id')
    group_id = kwargs.get('group_id')
    args = kwargs.get('args', [])
    user_level = kwargs.get('user_level', 0)
    sender_role = kwargs.get('sender_role', None)
    
    # 检查用户权限，需要Admin或Root权限
    # Root用户总是可以使用该命令，无论群组是否配置
    # 群主(owner)和管理员(admin)也视为具有管理员权限
    is_owner_or_admin = sender_role in ["owner", "admin"]
    if str(user_id) != str(context.get_config_value("Root_user")) and user_level < 1 and not is_owner_or_admin:
        return CommandResponse.text("⚠️ 需要管理员权限")
    
    if not args:
        return CommandResponse.text("❌ 用法：/bancommand add/rm 命令")
    
    action = args[0].lower()
    
    if action not in ['add', 'rm']:
        return CommandResponse.text("❌ 无效的操作，支持的操作：add, rm")
    
    if len(args) < 2:
        return CommandResponse.text("❌ 请指定要操作的命令")
    
    command_name = args[1].lower().lstrip('/')
    
    try:
        # 加载群组权限配置
        permissions = load_permissions(context, group_id)
        
        # 确保blacklisted_commands字段存在
        if 'blacklisted_commands' not in permissions:
            permissions['blacklisted_commands'] = []
        
        # 添加或移除命令
        if action == 'add':
            if command_name not in permissions['blacklisted_commands']:
                permissions['blacklisted_commands'].append(command_name)
                save_permissions(context, permissions, group_id)
                return CommandResponse.text(f"✅ 已将命令 '{command_name}' 添加到禁用列表")
            else:
                return CommandResponse.text(f"⚠️ 命令 '{command_name}' 已经在禁用列表中")
        else:  # rm
            if command_name in permissions['blacklisted_commands']:
                permissions['blacklisted_commands'].remove(command_name)
                save_permissions(context, permissions, group_id)
                return CommandResponse.text(f"✅ 已将命令 '{command_name}' 从禁用列表中移除")
            else:
                return CommandResponse.text(f"⚠️ 命令 '{command_name}' 不在禁用列表中")
    except Exception as e:
        log_exception(logger, "处理封禁命令时发生异常", e)
        return CommandResponse.text("🛑 内部错误")

def is_command_banned(context: BotContext, command_name: str, group_id: str) -> bool:
    """检查命令是否被禁用。"""
    try:
        if not group_id:
            return False
        
        # 加载群组权限配置
        permissions = load_permissions(context, group_id)
        
        # 检查命令是否在黑名单中
        blacklisted_commands = permissions.get('blacklisted_commands', [])
        if command_name in blacklisted_commands:
            return True
        
        # 检查别名也被禁用
        # 检查中文命令到英文命令的映射
        from commands.command_dispatcher import CHINESE_COMMAND_MAPPING
        if command_name in CHINESE_COMMAND_MAPPING:
            english_command = CHINESE_COMMAND_MAPPING[command_name]
            if english_command in blacklisted_commands:
                return True
        
        # 检查英文命令到中文命令的映射
        from commands.command_dispatcher.command_registry import ENGLISH_COMMAND_MAPPING
        if command_name in ENGLISH_COMMAND_MAPPING:
            chinese_commands = ENGLISH_COMMAND_MAPPING[command_name]
            if isinstance(chinese_commands, list):
                for chinese_cmd in chinese_commands:
                    if chinese_cmd in blacklisted_commands:
                        return True
            elif chinese_commands in blacklisted_commands:
                return True
        
        return False
    except Exception as e:
        logger.error(f"检查命令是否被禁用时发生异常: {e}")
        return False