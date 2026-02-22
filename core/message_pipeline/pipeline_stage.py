# core/message_pipeline/pipeline_stage.py
# 管道阶段基类，定义不同的消息处理阶段

from enum import Enum
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from .message_context import MessageContext

class StageType(Enum):
    """管道阶段类型"""
    PRE_PROCESS = "pre_process"  # 预处理阶段
    COMMAND_DETECTION = "command_detection"  # 命令检测阶段
    COMMAND_PROCESSING = "command_processing"  # 命令处理阶段
    AI_PROCESSING = "ai_processing"  # AI处理阶段
    POST_PROCESS = "post_process"  # 后处理阶段
    RESPONSE_GENERATION = "response_generation"  # 响应生成阶段

class PipelineStage(ABC):
    """管道阶段基类"""
    
    def __init__(self, name: str, stage_type: StageType):
        self.name = name  # 阶段名称
        self.stage_type = stage_type  # 阶段类型
        self.processors: List['MessageProcessor'] = []  # 该阶段的处理器列表
        
    @abstractmethod
    async def execute(self, context: MessageContext) -> bool:
        """执行阶段处理
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否应该继续执行后续阶段
        """
        pass
    
    def add_processor(self, processor: 'MessageProcessor'):
        """添加处理器到该阶段"""
        self.processors.append(processor)
    
    def get_processor(self, name: str) -> 'MessageProcessor':
        """根据名称获取处理器"""
        for processor in self.processors:
            if processor.name == name:
                return processor
        return None
    
    def remove_processor(self, name: str):
        """根据名称移除处理器"""
        self.processors = [p for p in self.processors if p.name != name]
    
    def __str__(self) -> str:
        return f"PipelineStage(name={self.name}, type={self.stage_type.value}, processors={len(self.processors)})"
