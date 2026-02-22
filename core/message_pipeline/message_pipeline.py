# core/message_pipeline/message_pipeline.py
# 消息管道核心类，管理和执行各个处理阶段

from typing import Dict, List, Any, Optional
from logger_config import get_logger
from .message_context import MessageContext
from .pipeline_stage import PipelineStage, StageType
from .processor import MessageProcessor

logger = get_logger("MessagePipeline")

class MessagePipeline:
    """消息处理管道，管理多个处理阶段"""
    
    def __init__(self):
        self.stages: Dict[StageType, PipelineStage] = {}  # 按类型存储阶段
        self.stage_order: List[StageType] = [  # 阶段执行顺序
            StageType.PRE_PROCESS,
            StageType.COMMAND_DETECTION,
            StageType.COMMAND_PROCESSING,
            StageType.AI_PROCESSING,
            StageType.POST_PROCESS,
            StageType.RESPONSE_GENERATION
        ]
    
    def add_stage(self, stage: PipelineStage):
        """添加处理阶段"""
        self.stages[stage.stage_type] = stage
        logger.debug(f"Added stage: {stage.name} ({len(stage.processors)} processors)")
    
    def get_stage(self, stage_type: StageType) -> Optional[PipelineStage]:
        """获取指定类型的阶段"""
        return self.stages.get(stage_type)
    
    def add_processor(self, stage_type: StageType, processor: MessageProcessor):
        """向指定阶段添加处理器"""
        if stage_type in self.stages:
            self.stages[stage_type].add_processor(processor)
            logger.debug(f"Added processor '{processor.name}' (priority {processor.priority}) to stage '{stage_type.value}'")
        else:
            logger.error(f"Cannot add processor to non-existent stage: {stage_type.value}")
    
    async def process_message(self, context: MessageContext) -> bool:
        """处理消息，按顺序执行各个阶段
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否成功处理
        """
        logger.debug(f"Processing message with pipeline: {context}")
        
        for stage_type in self.stage_order:
            if stage_type not in self.stages:
                logger.debug(f"Skipping missing stage: {stage_type.value}")
                continue
            
            stage = self.stages[stage_type]
            logger.debug(f"Executing stage: {stage.name}")
            
            # 执行阶段处理
            try:
                should_continue = await stage.execute(context)
                if not should_continue:
                    logger.debug(f"Stage {stage.name} requested to stop processing")
                    break
            except Exception as e:
                logger.error(f"Error executing stage {stage.name}: {e}", exc_info=True)
                # 继续执行后续阶段，不要因为一个阶段失败而中断整个流程
        
        logger.debug(f"Message processing completed: {context}")
        return context.processed
    
    def get_stage_order(self) -> List[StageType]:
        """获取阶段执行顺序"""
        return self.stage_order.copy()
    
    def set_stage_order(self, order: List[StageType]):
        """设置阶段执行顺序"""
        self.stage_order = order
        logger.info(f"Set stage order: {[stage.value for stage in order]}")
    
    def add_stage_after(self, new_stage: PipelineStage, after_stage_type: StageType):
        """在指定阶段后添加新阶段"""
        self.add_stage(new_stage)
        if after_stage_type in self.stage_order:
            index = self.stage_order.index(after_stage_type)
            self.stage_order.insert(index + 1, new_stage.stage_type)
        else:
            self.stage_order.append(new_stage.stage_type)
    
    def add_stage_before(self, new_stage: PipelineStage, before_stage_type: StageType):
        """在指定阶段前添加新阶段"""
        self.add_stage(new_stage)
        if before_stage_type in self.stage_order:
            index = self.stage_order.index(before_stage_type)
            self.stage_order.insert(index, new_stage.stage_type)
        else:
            self.stage_order.insert(0, new_stage.stage_type)
