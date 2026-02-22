# commands/command_dispatcher/command_registry.py
# 负责命令注册和映射

import os
import json
from logger_config import get_logger
from core.bot_context import BotContext

logger = get_logger("CommandRegistry")

# 命令处理器映射字典
COMMAND_HANDLERS = {}

# 命令集合（所有命令只要满足条件就全局可用）
GLOBAL_COMMANDS = set()

# 中文命令到英文命令的映射
CHINESE_COMMAND_MAPPING = {}

# 英文命令到中文命令的映射
ENGLISH_COMMAND_MAPPING = {}

# 用于存储命令返回值的字典（仅用于兼容旧版命令）
_command_responses = {}

# 用于生成唯一的临时消息ID
_response_counter = 0

# 获取临时消息ID的函数
def _get_temp_message_id():
    global _response_counter
    _response_counter += 1
    return f"temp_{_response_counter}"

def initialize_command_mappings(config):
    """从配置文件初始化中文命令映射
    
    Args:
        config: 包含commands配置的字典
    """
    global CHINESE_COMMAND_MAPPING, GLOBAL_COMMANDS
    
    # 清空现有的映射
    CHINESE_COMMAND_MAPPING.clear()
    GLOBAL_COMMANDS.clear()
    
    # 从配置中加载中文命令映射
    commands_config = config.get("commands", {})
    for en_command, cmd_config in commands_config.items():
        # 获取中文命令别名列表
        chinese_names = cmd_config.get("chinese_names", [])
        
        if chinese_names:
            # 确保chinese_names是列表
            if isinstance(chinese_names, str):
                chinese_names = [chinese_names]
            
            # 添加中文命令到英文命令的映射
            for zh_command in chinese_names:
                CHINESE_COMMAND_MAPPING[zh_command] = en_command
        
        # 添加命令到GLOBAL_COMMANDS中
        GLOBAL_COMMANDS.add(en_command)
        for zh_command in chinese_names:
            GLOBAL_COMMANDS.add(zh_command)
    
    logger.info(f"已从配置文件加载 {len(CHINESE_COMMAND_MAPPING)} 个中文命令映射")

# 注意: register_command装饰器已被移除，命令现在仅通过配置文件注册

async def _is_user_blacklisted(context: BotContext, group_id: str, user_id: str) -> bool:
    """检查用户是否在群组黑名单中"""
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
            return False
    
    # 检查是否存在blacklist以及用户是否在其中
    if "blacklist" in group_config and user_id in group_config["blacklist"]:
        return True
    
    return False