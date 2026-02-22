# core/message_pipeline/pipeline_manager.py
# 管道管理器，负责初始化和管理消息处理管道

from logger_config import get_logger
from .message_pipeline import MessagePipeline
from .stages.pre_process_stage import PreProcessStage
from .stages.command_detection_stage import CommandDetectionStage
from .stages.command_processing_stage import CommandProcessingStage
from .stages.post_process_stage import PostProcessStage
from .stages.response_generation_stage import ResponseGenerationStage
from .message_context import MessageContext
from .pipeline_stage import StageType
from core.bot_context import BotContext as CoreBotContext

logger = get_logger("PipelineManager")

class PipelineManager:
    """管道管理器，负责初始化和管理消息处理管道"""
    
    def __init__(self, core_context: CoreBotContext):
        self.core_context = core_context
        self.pipeline = MessagePipeline()
        self._initialize_pipeline()
    
    def _initialize_pipeline(self):
        """初始化管道的各个阶段"""
        logger.debug("Initializing message processing pipeline...")
        
        # 添加各个阶段
        self.pipeline.add_stage(PreProcessStage())
        self.pipeline.add_stage(CommandDetectionStage())
        self.pipeline.add_stage(CommandProcessingStage())
        # AI处理阶段暂时移除，保留架构扩展点
        self.pipeline.add_stage(PostProcessStage())
        self.pipeline.add_stage(ResponseGenerationStage())
        
        # 添加处理器到相应阶段
        from .processors.command_detector import CommandDetector
        from .processors.command_processor import CommandProcessor
        
        # 添加命令检测器到命令检测阶段
        self.pipeline.add_processor(StageType.COMMAND_DETECTION, CommandDetector())
        
        # 添加命令处理器到命令处理阶段
        self.pipeline.add_processor(StageType.COMMAND_PROCESSING, CommandProcessor())
        
        logger.debug("Message processing pipeline initialized successfully")
    
    def get_pipeline(self) -> MessagePipeline:
        """获取消息处理管道"""
        return self.pipeline
    
    async def process_message(self, event: dict) -> bool:
        """处理消息，创建上下文并通过管道处理
        
        Args:
            event: 原始消息事件
            
        Returns:
            bool: 是否成功处理
        """
        # 创建消息上下文
        context = MessageContext(self.core_context, event)
        
        # 通过管道处理消息
        return await self.pipeline.process_message(context)
    
    def add_processor(self, stage_type, processor):
        """向指定阶段添加处理器"""
        self.pipeline.add_processor(stage_type, processor)
    
    def get_stage(self, stage_type):
        """获取指定类型的阶段"""
        return self.pipeline.get_stage(stage_type)
