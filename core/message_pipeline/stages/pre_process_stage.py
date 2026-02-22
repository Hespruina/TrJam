# core/message_pipeline/stages/pre_process_stage.py
# 预处理阶段，处理消息的基本验证、过滤等

from logger_config import get_logger
from ..pipeline_stage import PipelineStage, StageType
from ..message_context import MessageContext
from ..processor import MessageProcessor

logger = get_logger("PreProcessStage")

class PreProcessStage(PipelineStage):
    """预处理阶段"""
    
    def __init__(self):
        super().__init__("pre_process", StageType.PRE_PROCESS)
    
    async def execute(self, context: MessageContext) -> bool:
        """执行预处理
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续执行后续阶段
        """
        logger.debug(f"Executing pre-process stage for: {context}")
        
        # 按优先级顺序执行处理器
        sorted_processors = sorted(self.processors, key=lambda p: p.priority, reverse=True)
        
        for processor in sorted_processors:
            if processor.can_handle(context):
                try:
                    logger.debug(f"Executing pre-processor: {processor.name}")
                    result = await processor.process(context)
                    if not context.should_continue_processing():
                        logger.debug(f"Message processed by pre-processor {processor.name}")
                        return False
                except Exception as e:
                    logger.error(f"Error in pre-processor {processor.name}: {e}", exc_info=True)
        
        return True
