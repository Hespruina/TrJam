# commands/help_command/help_formatter.py
# 负责格式化帮助信息文本

from logger_config import get_logger
from core.bot_context import BotContext

logger = get_logger("HelpCommandFormatter")

def get_help_info(context: BotContext, user_id: str, group_id: str, is_configured=True, sender_role: str = None) -> str:
    """生成并返回帮助信息，严格按照用户权限显示命令。"""
    logger.debug(f"开始生成帮助信息，用户ID: {user_id}，群ID: {group_id}，用户角色: {sender_role}")
    perm_level = 0
    if user_id is not None and group_id is not None:
        from commands.permission_manager import check_permission
        perm_level = check_permission(context, user_id, group_id, sender_role)
    logger.debug(f"用户 {user_id} 在群 {group_id} 的权限级别: {perm_level}")

    perm_mapping = {"User": 0, "Admin": 1, "Root": 2}
    help_sections = {}
    
    # 导入黑名单检查函数
    from commands.bancommand_command import is_command_banned

    if not is_configured:
        # 未配置群聊时，严格按照用户权限显示命令
        all_commands = []
        
        # 从commands.yml中读取命令，只显示用户有权限的命令
        for cmd, config in context.config.get("commands", {}).items():
            if not config.get("hidden", False):
                required_level = perm_mapping.get(config.get("permission", "User"), 0)
                # 严格按照用户权限显示命令
                if perm_level >= required_level:
                    base_help_line = f"/{cmd} {config.get('usage', '').replace(f'/{cmd}', '').strip()} - {config.get('description', '')}"
                    help_line = f"✅ {base_help_line}"
                    all_commands.append(help_line)
                    logger.debug(f"添加命令到未配置群帮助: /{cmd}")
        
        # 从features中读取功能，只显示用户有权限的功能
        for feature_key, feature_config in context.config.get("features", {}).items():
            if feature_config.get("enabled", False):
                required_level = perm_mapping.get(feature_config.get("permission", "User"), 0)
                # 严格按照用户权限显示功能
                if perm_level >= required_level:
                    description = feature_config.get('description', f'{feature_key} 功能')
                    usage = feature_config.get('usage', '')
                    triggers = feature_config.get('trigger', [])
                    trigger_text = ""
                    if isinstance(triggers, list):
                        trigger_text = f" (触发词: {', '.join(triggers)})" if triggers else ""
                    elif isinstance(triggers, str):
                        trigger_text = f" (触发词: {triggers})"
                    
                    base_help_line = f"{usage} - {description}{trigger_text}"
                    help_line = f"✅ {base_help_line}"
                    if help_line not in all_commands:
                        all_commands.append(help_line)
                        logger.debug(f"添加功能到未配置群帮助: {feature_key}")
        
        # 如果没有找到任何命令，使用默认列表
        if not all_commands:
            all_commands = [
                "✅ /quote 或 名言 - 生成名言图片",
                "✅ /help - 显示帮助信息"
            ]
        
        return "\n".join([
            "✅ = 可用功能",
            "\n功能列表:",
            "\n".join(all_commands)
        ])

    logger.debug("初始化命令和功能分组字典")
    command_count = 0
    
    # 获取所有主程序命令
    all_commands_dict = context.config.get("commands", {})
    
    # 严格按照用户权限显示命令
    for cmd, config in all_commands_dict.items():
        if config.get("hidden", False):
            logger.debug(f"跳过隐藏命令: {cmd}")
            continue
        required_level = perm_mapping.get(config.get("permission", "User"), 0)
        if perm_level >= required_level:
            category = config.get("category", config.get("permission", "User"))
            if category not in help_sections:
                help_sections[category] = []
            
            # 检查命令是否被禁用
            is_blacklisted = is_command_banned(context, cmd, group_id)
            
            # 构建命令行文本
            base_help_line = f"/{cmd} {config.get('usage', '').replace(f'/{cmd}', '').strip()} - {config.get('description', '')}"
            
            if is_blacklisted:
                help_line = f"❌ {base_help_line} [已禁用]"
            else:
                help_line = f"✅ {base_help_line}"
            
            help_sections[category].append(help_line)
            command_count += 1
            logger.debug(f"添加命令到帮助信息: /{cmd} (分类: {category}, 被禁用: {is_blacklisted})")
        else:
            logger.debug(f"用户无权限查看命令: /{cmd} (所需权限: {required_level})")

    logger.debug(f"开始遍历特殊功能配置")
    feature_count = 0
    # 严格按照用户权限显示功能
    for feature_key, feature_config in context.config.get("features", {}).items():
        if not feature_config.get("enabled", False):
            logger.debug(f"跳过未启用的功能: {feature_key}")
            continue
        required_level = perm_mapping.get(feature_config.get("permission", "User"), 0)
        if perm_level >= required_level:
            category_key = feature_config.get("category", "通用")
            if category_key == "通用":
                 if "特殊功能" in context.config.get("command_categories", {}):
                     category_display_name = context.config["command_categories"]["特殊功能"]["name"]
                     category_emoji = context.config["command_categories"]["特殊功能"]["emoji"]
                 elif "通用" in context.config.get("command_categories", {}):
                     category_display_name = context.config["command_categories"]["通用"]["name"]
                     category_emoji = context.config["command_categories"]["通用"]["emoji"]
                 else:
                     category_display_name = "特殊功能"
                     category_emoji = "✨"
            else:
                 category = category_key
                 category_config = context.config.get("command_categories", {}).get(category, {})
                 category_display_name = category_config.get("name", category)
                 category_emoji = category_config.get("emoji", "")
            if category not in context.config.get("command_categories", {}):
                 if "特殊功能" in context.config.get("command_categories", {}):
                     category_display_name = context.config["command_categories"]["特殊功能"]["name"]
                     category_emoji = context.config["command_categories"]["特殊功能"]["emoji"]
                 elif "通用" in context.config.get("command_categories", {}):
                     category_display_name = context.config["command_categories"]["通用"]["name"]
                     category_emoji = context.config["command_categories"]["通用"]["emoji"]
                 else:
                     category_display_name = "特殊功能"
                     category_emoji = "✨"
            final_category_key = category_display_name
            if final_category_key not in help_sections:
                help_sections[final_category_key] = []
            description = feature_config.get('description', f'{feature_key} 功能')
            usage = feature_config.get('usage', '')
            triggers = feature_config.get('trigger', [])
            trigger_text = ""
            if isinstance(triggers, list):
                trigger_text = f" (触发词: {', '.join(triggers)})" if triggers else ""
            elif isinstance(triggers, str):
                trigger_text = f" (触发词: {triggers})"
            
            # 检查功能对应的命令是否被禁用（如果功能有对应的命令）
            is_blacklisted = False
            if usage.startswith('/') and group_id:
                cmd_name = usage.lstrip('/').split()[0]
                is_blacklisted = is_command_banned(context, cmd_name, group_id)
            
            # 构建功能行文本
            base_help_line = f"{usage} - {description}{trigger_text}"
            
            if is_blacklisted:
                help_line = f"❌ {base_help_line} [已禁用]"
            else:
                help_line = f"✅ {base_help_line}"
            
            if help_line not in help_sections[final_category_key]:
                help_sections[final_category_key].append(help_line)
                feature_count += 1
            logger.debug(f"添加功能到帮助信息: {feature_key} (分类: {final_category_key}, 被禁用: {is_blacklisted})")
        else:
            logger.debug(f"用户无权限查看功能: {feature_key} (所需权限: {required_level})")

    logger.debug(f"共添加 {command_count} 个命令和 {feature_count} 个功能到帮助信息")
    help_parts = []
    # 添加图例说明
    help_parts.append("✅ = 可用功能 | ❌ = 已禁用功能")
    help_parts.append("")
    logger.debug("开始构建帮助信息")
    for category_key, cat_config in context.config.get("command_categories", {}).items():
        display_name = cat_config["name"]
        if display_name in help_sections and help_sections[display_name]:
            emoji = cat_config.get("emoji", "")
            help_parts.append(f"{emoji} {display_name}:")
            help_parts.extend(sorted(help_sections[display_name]))
            help_parts.append("")
            logger.debug(f"添加分类到帮助信息: {display_name}，条目数: {len(help_sections[display_name])}")

    if not help_parts or (len(help_parts) == help_parts.count("")):
        return "❌ 当前没有可用的命令或功能。"

    while help_parts and help_parts[-1] == "":
        help_parts.pop()

    return "\n".join(help_parts)