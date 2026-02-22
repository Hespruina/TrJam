# core/message_pipeline/stages/post_process_stage.py
# 后处理阶段，对处理结果进行后处理

from logger_config import get_logger
from ..pipeline_stage import PipelineStage, StageType
from ..message_context import MessageContext

logger = get_logger("PostProcessStage")

class PostProcessStage(PipelineStage):
    """后处理阶段"""
    
    def __init__(self):
        super().__init__("post_process", StageType.POST_PROCESS)
    
    async def execute(self, context: MessageContext) -> bool:
        """执行后处理
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续执行后续阶段
        """
        logger.debug(f"Executing post-process stage for: {context}")
        
        # 按优先级顺序执行处理器
        sorted_processors = sorted(self.processors, key=lambda p: p.priority, reverse=True)
        
        for processor in sorted_processors:
            if processor.can_handle(context):
                try:
                    logger.debug(f"Executing post-processor: {processor.name}")
                    result = await processor.process(context)
                except Exception as e:
                    logger.error(f"Error in post-processor {processor.name}: {e}", exc_info=True)
        
        return True
