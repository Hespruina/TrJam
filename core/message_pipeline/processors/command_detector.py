# core/message_pipeline/processors/command_detector.py
# 命令检测处理器，检测消息是否为命令

from logger_config import get_logger
from ..processor import MessageProcessor
from ..message_context import MessageContext
from utils.message_utils import parse_message

logger = get_logger("CommandDetector")

class CommandDetector(MessageProcessor):
    """命令检测处理器"""
    
    def __init__(self):
        super().__init__("command_detector", priority=10)
    
    def can_handle(self, context: MessageContext) -> bool:
        """判断是否可以处理该消息"""
        return context.post_type == 'message'
    
    async def process(self, context: MessageContext) -> bool:
        """检测消息是否为命令
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否检测到命令
        """
        # 解析消息内容
        raw_message = context.event.get('message', '')
        original_message = parse_message(raw_message).strip()
        
        # 检查是否为命令
        is_command = False
        
        # 检查是否以斜杠开头
        if original_message.startswith('/'):
            is_command = True
            logger.debug(f"Command detected (slash): {original_message}")
        else:
            # 检查是否为中文命令
            from commands.command_dispatcher import CHINESE_COMMAND_MAPPING
            first_word = original_message.strip().split()[0] if original_message.strip() else ""
            if first_word in CHINESE_COMMAND_MAPPING or first_word in ['赞我']:
                is_command = True
                logger.debug(f"Command detected (Chinese): {original_message}")
        
        if is_command:
            # 存储命令信息到上下文
            context.add_extra_data("original_message", original_message)
            context.add_extra_data("raw_message", raw_message)
            return True
        
        return False
