# core/message_pipeline/stages/command_processing_stage.py
# 命令处理阶段，处理检测到的命令

from logger_config import get_logger
from ..pipeline_stage import PipelineStage, StageType
from ..message_context import MessageContext

logger = get_logger("CommandProcessingStage")

class CommandProcessingStage(PipelineStage):
    """命令处理阶段"""
    
    def __init__(self):
        super().__init__("command_processing", StageType.COMMAND_PROCESSING)
    
    async def execute(self, context: MessageContext) -> bool:
        """执行命令处理
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续执行后续阶段
        """
        logger.debug(f"Executing command processing stage for: {context}")
        
        # 检查是否检测到命令
        if not context.get_extra_data("command_detected", False):
            logger.debug("No command detected, skipping command processing")
            return True
        
        # 按优先级顺序执行处理器
        sorted_processors = sorted(self.processors, key=lambda p: p.priority, reverse=True)
        
        for processor in sorted_processors:
            if processor.can_handle(context):
                try:
                    logger.debug(f"Executing command processor: {processor.name}")
                    result = await processor.process(context)
                    if not context.should_continue_processing():
                        logger.debug(f"Command processed by {processor.name}")
                        return False
                except Exception as e:
                    logger.error(f"Error in command processor {processor.name}: {e}", exc_info=True)
        
        return True
