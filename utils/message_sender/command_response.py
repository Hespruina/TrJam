# utils/message_sender/command_response.py
# 命令响应封装类

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.message_sender.message_builder import MessageBuilder

class CommandResponse:
    """命令响应封装类，用于统一命令返回格式"""
    
    def __init__(self, response_type: str, data: Any):
        self.type = response_type
        self.data = data
    
    @classmethod
    def none(cls) -> 'CommandResponse':
        """创建一个空响应"""
        return cls("none", None)
    
    @classmethod
    def text(cls, text: str) -> 'CommandResponse':
        """创建一个文本响应"""
        return cls("text", text)
    
    @classmethod
    def builder(cls, builder: 'MessageBuilder') -> 'CommandResponse':
        """创建一个基于MessageBuilder的响应"""
        return cls("builder", builder)
    
    @classmethod
    def raw(cls, message: list) -> 'CommandResponse':
        """创建一个原始消息段响应"""
        return cls("raw", message)