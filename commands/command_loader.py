# commands/command_loader.py
# 负责根据配置动态加载命令处理器

import importlib
from logger_config import get_logger

logger = get_logger("CommandLoader")

def load_command_handlers(config):
    """根据配置文件动态加载命令处理器"""
    commands_config = config.get("commands", {})
    
    loaded_count = 0
    for command_name, cmd_config in commands_config.items():
        try:
            module_name = cmd_config.get("module")
            function_name = cmd_config.get("function")
            
            if module_name and function_name:
                # 动态导入模块
                module = importlib.import_module(module_name)
                # 获取函数
                handler_func = getattr(module, function_name)
                # 注册命令处理器
                from commands.command_dispatcher import COMMAND_HANDLERS
                COMMAND_HANDLERS[command_name] = handler_func
                logger.debug(f"已动态加载命令 '{command_name}' 的处理器: {module_name}.{function_name}")
                loaded_count += 1
            else:
                logger.warning(f"命令 '{command_name}' 缺少 module 或 function 配置")
        except (ImportError, AttributeError) as e:
            logger.error(f"无法加载命令 '{command_name}' 的处理器: {e}")
        except Exception as e:
            logger.error(f"加载命令 '{command_name}' 时发生未知错误: {e}")
    
    logger.info(f"已完成动态加载 {loaded_count} 个命令处理器")