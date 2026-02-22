# core/message_pipeline/processor.py
# 消息处理器基类，定义处理器的基本接口

from abc import ABC, abstractmethod
from typing import Any, Dict
from .message_context import MessageContext

class MessageProcessor(ABC):
    """消息处理器基类"""
    
    def __init__(self, name: str, priority: int = 0):
        self.name = name  # 处理器名称
        self.priority = priority  # 优先级，数字越大优先级越高
        
    @abstractmethod
    async def process(self, context: MessageContext) -> bool:
        """处理消息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否成功处理，True表示处理完成，False表示继续处理
        """
        pass
    
    def can_handle(self, context: MessageContext) -> bool:
        """判断是否可以处理该消息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否可以处理
        """
        return True
    
    def get_name(self) -> str:
        """获取处理器名称"""
        return self.name
    
    def get_priority(self) -> int:
        """获取处理器优先级"""
        return self.priority
    
    def __str__(self) -> str:
        return f"MessageProcessor(name={self.name}, priority={self.priority})"
    
    def __repr__(self) -> str:
        return self.__str__()
