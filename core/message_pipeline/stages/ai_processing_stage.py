# core/message_pipeline/stages/ai_processing_stage.py
# AI处理阶段，处理非命令消息的AI响应

from logger_config import get_logger
from ..pipeline_stage import PipelineStage, StageType
from ..message_context import MessageContext

logger = get_logger("AIProcessingStage")

class AIProcessingStage(PipelineStage):
    """AI处理阶段"""
    
    def __init__(self):
        super().__init__("ai_processing", StageType.AI_PROCESSING)
    
    async def execute(self, context: MessageContext) -> bool:
        """执行AI处理
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续执行后续阶段
        """
        logger.debug(f"Executing AI processing stage for: {context}")
        
        # 如果消息已被处理（例如被命令处理器处理），则跳过AI处理
        if not context.should_continue_processing():
            logger.debug("Message already processed, skipping AI processing")
            return True
        
        # 检查是否检测到命令，如果检测到命令但未被处理，也跳过AI处理
        if context.get_extra_data("command_detected", False):
            logger.debug("Command detected but not processed, skipping AI processing")
            return True
        
        # 按优先级顺序执行处理器
        sorted_processors = sorted(self.processors, key=lambda p: p.priority, reverse=True)
        
        for processor in sorted_processors:
            if processor.can_handle(context):
                try:
                    logger.debug(f"Executing AI processor: {processor.name}")
                    result = await processor.process(context)
                    if not context.should_continue_processing():
                        logger.debug(f"Message processed by AI processor {processor.name}")
                        return False
                except Exception as e:
                    logger.error(f"Error in AI processor {processor.name}: {e}", exc_info=True)
        
        return True
