# core/message_pipeline/processors/command_processor.py
# 命令处理器，处理检测到的命令

from logger_config import get_logger
from ..processor import MessageProcessor
from ..message_context import MessageContext
from commands.command_dispatcher import dispatch_command

logger = get_logger("CommandProcessor")

class CommandProcessor(MessageProcessor):
    """命令处理器"""
    
    def __init__(self):
        super().__init__("command_processor", priority=10)
    
    def can_handle(self, context: MessageContext) -> bool:
        """判断是否可以处理该消息"""
        return context.post_type == 'message' and context.get_extra_data("command_detected", False)
    
    async def process(self, context: MessageContext) -> bool:
        """处理命令
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否成功处理
        """
        try:
            # 获取命令信息
            original_message = context.get_extra_data("original_message")
            raw_message = context.get_extra_data("raw_message")
            
            user_id = context.user_id
            group_id = context.group_id
            message_id = context.message_id
            
            # 获取发送者昵称
            nickname = "未知用户"
            if 'sender' in context.event:
                sender = context.event['sender']
                nickname = sender.get('card') or sender.get('nickname', '未知用户')
            
            # 获取发送者角色
            sender_role = context.event.get('sender', {}).get('role')
            
            logger.debug(f"Processing command: {original_message} from {user_id} in {group_id}")
            
            # 调用命令分发器处理命令
            result = await dispatch_command(
                context.core_context, 
                original_message, 
                user_id, 
                group_id, 
                nickname, 
                raw_message=raw_message, 
                websocket=context.core_context.websocket, 
                message_id=message_id, 
                sender_role=sender_role
            )
            
            # 命令处理结果会由dispatch_command直接发送，这里标记为已处理
            context.set_processed("command_processor")
            logger.debug(f"Command processed: {original_message}")
            
            return True
        except Exception as e:
            logger.error(f"Error processing command: {e}", exc_info=True)
            return False
