# commands/help_command/help_data.py
# 负责生成帮助组数据

from logger_config import get_logger
from core.bot_context import BotContext

logger = get_logger("HelpCommandData")

async def generate_help_groups(context: BotContext, user_id: str, group_id: str, is_configured: bool, is_master: bool, sender_role: str = None, **kwargs) -> tuple:
    """生成帮助组数据，返回(help_groups, permission_blocked_count, blacklist_blocked_count)"""
    # 统计被屏蔽的命令数量
    permission_blocked_count = 0
    blacklist_blocked_count = 0
    
    # 权限映射表
    perm_mapping = {"User": 0, "Admin": 1, "Root": 2}
    
    # 检查用户权限（只做一次）
    perm_level = 0
    if user_id is not None and group_id is not None:
        from commands.permission_manager import check_permission
        perm_level = check_permission(context, user_id, group_id, sender_role)
    
    # 导入is_command_banned函数（只做一次）
    is_command_banned_func = None
    if is_configured and group_id:
        from commands.bancommand_command import is_command_banned
        is_command_banned_func = is_command_banned
    
    if not is_configured:
        # 未配置群聊时，根据用户权限显示命令
        all_commands = []
        
        # 从commands.yml中读取命令，只显示用户有权限的命令
        for cmd, config in context.config.get("commands", {}).items():
            if config.get("hidden", False):
                continue
                
            required_level = perm_mapping.get(config.get("permission", "User"), 0)
            # 严格按照用户权限显示命令，不额外显示管理员命令
            if perm_level >= required_level:
                all_commands.append({
                    "title": f"/{cmd}",
                    "eg": f"/{cmd} {config.get('usage', '').replace(f'/{cmd}', '').strip()}",
                    "desc": config.get("description", "")
                })
            else:
                permission_blocked_count += 1
        
        # 从features中读取功能，只显示用户有权限的功能
        for feature_key, feature_config in context.config.get("features", {}).items():
            if not feature_config.get("enabled", False):
                continue
                
            required_level = perm_mapping.get(feature_config.get("permission", "User"), 0)
            # 严格按照用户权限显示功能
            if perm_level >= required_level:
                description = feature_config.get('description', f'{feature_key} 功能')
                usage = feature_config.get('usage', '')
                triggers = feature_config.get('trigger', [])
                
                # 构建触发词文本
                trigger_text = ""
                if triggers:
                    if isinstance(triggers, list):
                        trigger_text = f" (触发词: {', '.join(triggers)})"
                    else:
                        trigger_text = f" (触发词: {triggers})"
                
                all_commands.append({
                    "title": usage,
                    "eg": usage,
                    "desc": f"{description}{trigger_text}"
                })
            else:
                permission_blocked_count += 1
        
        # 如果没有找到任何命令，使用默认列表
        if not all_commands:
            all_commands = [
                {"title": "/quote", "eg": "/quote 或 名言", "desc": "生成名言图片"},
                {"title": "/help", "eg": "/help", "desc": "显示帮助信息"}
            ]
        
        return [{"group": "📚 通用功能", "auth": "user", "list": all_commands}], permission_blocked_count, blacklist_blocked_count
    else:
        # 已配置群聊时，根据用户权限和群设置显示命令
        command_categories = {}
        
        # 处理主程序命令，严格按照用户权限显示
        all_commands_dict = context.config.get("commands", {})
        
        for cmd, config in all_commands_dict.items():
            if config.get("hidden", False):
                continue
                
            required_level = perm_mapping.get(config.get("permission", "User"), 0)
            # 严格按照用户权限显示命令
            if perm_level >= required_level:
                category = config.get("category", "通用功能")
                
                # 检查命令是否被禁用
                is_blacklisted = is_command_banned_func(context, cmd, group_id) if is_command_banned_func else False
                
                # 构建命令信息
                command_info = {
                    "title": f"/{cmd}",
                    "eg": f"/{cmd} {config.get('usage', '').replace(f'/{cmd}', '').strip()}",
                    "desc": config.get("description", "")
                }
                
                # 如果命令被禁用，添加标记
                if is_blacklisted:
                    command_info["disabled"] = True
                    command_info["desc"] += " [已禁用]"
                    blacklist_blocked_count += 1
                
                # 添加到分类
                if category not in command_categories:
                    command_categories[category] = []
                command_categories[category].append(command_info)
            else:
                permission_blocked_count += 1
        
        # 处理功能，严格按照用户权限显示
        for feature_key, feature_config in context.config.get("features", {}).items():
            if not feature_config.get("enabled", False):
                continue
                
            required_level = perm_mapping.get(feature_config.get("permission", "User"), 0)
            # 严格按照用户权限显示功能
            if perm_level >= required_level:
                category = feature_config.get("category", "通用功能")
                
                description = feature_config.get('description', f'{feature_key} 功能')
                usage = feature_config.get('usage', '')
                triggers = feature_config.get('trigger', [])
                
                # 构建触发词文本
                trigger_text = ""
                if triggers:
                    if isinstance(triggers, list):
                        trigger_text = f" (触发词: {', '.join(triggers)})"
                    else:
                        trigger_text = f" (触发词: {triggers})"
                
                # 检查功能对应的命令是否被禁用（如果功能有对应的命令）
                is_blacklisted = False
                if usage.startswith('/') and is_command_banned_func:
                    cmd_name = usage.lstrip('/').split()[0]
                    is_blacklisted = is_command_banned_func(context, cmd_name, group_id)
                
                # 构建功能信息
                feature_info = {
                    "title": usage,
                    "eg": usage,
                    "desc": f"{description}{trigger_text}"
                }
                
                # 如果功能对应的命令被禁用，添加标记
                if is_blacklisted:
                    feature_info["disabled"] = True
                    feature_info["desc"] += " [已禁用]"
                    blacklist_blocked_count += 1
                
                # 添加到分类
                if category not in command_categories:
                    command_categories[category] = []
                command_categories[category].append(feature_info)
            else:
                permission_blocked_count += 1
        
        # 构建帮助组
        help_groups = []
        for category, commands in command_categories.items():
            # 只有当分类中至少有一个命令时才添加该分类
            if commands:
                help_groups.append({
                    "group": f"{category}",
                    "auth": "user",
                    "list": commands
                })
        
        # 如果没有生成任何帮助组，使用默认分类
        if not help_groups:
            help_groups = [{"group": "📚 通用功能", "auth": "user", "list": []}]
            
    return help_groups, permission_blocked_count, blacklist_blocked_count