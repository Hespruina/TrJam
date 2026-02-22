# core/message_pipeline/stages/command_detection_stage.py
# 命令检测阶段，检测消息是否为命令

from logger_config import get_logger
from ..pipeline_stage import PipelineStage, StageType
from ..message_context import MessageContext

logger = get_logger("CommandDetectionStage")

class CommandDetectionStage(PipelineStage):
    """命令检测阶段"""
    
    def __init__(self):
        super().__init__("command_detection", StageType.COMMAND_DETECTION)
    
    async def execute(self, context: MessageContext) -> bool:
        """执行命令检测
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续执行后续阶段
        """
        logger.debug(f"Executing command detection stage for: {context}")
        
        # 按优先级顺序执行处理器
        sorted_processors = sorted(self.processors, key=lambda p: p.priority, reverse=True)
        
        command_detected = False
        for processor in sorted_processors:
            if processor.can_handle(context):
                try:
                    logger.debug(f"Executing command detector: {processor.name}")
                    result = await processor.process(context)
                    if result:
                        command_detected = True
                        context.add_extra_data("command_detected", True)
                        logger.debug(f"Command detected by {processor.name}")
                        break
                except Exception as e:
                    logger.error(f"Error in command detector {processor.name}: {e}", exc_info=True)
        
        if not command_detected:
            context.add_extra_data("command_detected", False)
            logger.debug("No command detected")
        
        return True
