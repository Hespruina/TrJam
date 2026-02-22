# core/message_pipeline/__init__.py
# 消息处理管道，支持多阶段、可扩展的消息处理架构

from .message_context import MessageContext
from .pipeline_stage import PipelineStage
from .message_pipeline import MessagePipeline
from .processor import MessageProcessor

__all__ = [
    'MessageContext',
    'PipelineStage',
    'MessagePipeline',
    'MessageProcessor'
]
