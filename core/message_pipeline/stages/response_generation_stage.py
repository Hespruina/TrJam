# core/message_pipeline/stages/response_generation_stage.py
# 响应生成阶段，生成最终的响应

from logger_config import get_logger
from ..pipeline_stage import PipelineStage, StageType
from ..message_context import MessageContext

logger = get_logger("ResponseGenerationStage")

class ResponseGenerationStage(PipelineStage):
    """响应生成阶段"""
    
    def __init__(self):
        super().__init__("response_generation", StageType.RESPONSE_GENERATION)
    
    async def execute(self, context: MessageContext) -> bool:
        """执行响应生成
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续执行后续阶段
        """
        logger.debug(f"Executing response generation stage for: {context}")
        
        # 如果没有响应，跳过响应生成
        if context.response is None:
            logger.debug("No response to generate")
            return True
        
        # 按优先级顺序执行处理器
        sorted_processors = sorted(self.processors, key=lambda p: p.priority, reverse=True)
        
        response_sent = False
        for processor in sorted_processors:
            if processor.can_handle(context):
                try:
                    logger.debug(f"Executing response generator: {processor.name}")
                    result = await processor.process(context)
                    if result:
                        response_sent = True
                        logger.debug(f"Response sent by {processor.name}")
                        break
                except Exception as e:
                    logger.error(f"Error in response generator {processor.name}: {e}", exc_info=True)
        
        if not response_sent:
            logger.warning(f"No response generator could handle the response: {context.response}")
        
        return True
