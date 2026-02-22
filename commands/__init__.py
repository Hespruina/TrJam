# commands/__init__.py
# 导入所有命令处理器，以确保它们被注册

from .command_dispatcher import dispatch_command, COMMAND_HANDLERS

# 导入具体的命令处理器
import logging
logger = logging.getLogger("CommandInit")

# 导入各个命令模块
import commands.chat_command
import commands.sub_command

# 水印命令已移除

logger.info(f"已注册的命令处理器: {list(COMMAND_HANDLERS.keys())}")

__all__ = [
    'dispatch_command',
    'COMMAND_HANDLERS'
    # ... 可以列出所有公开的函数，但这不是必须的 ...
]