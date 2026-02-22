# core/message_pipeline/message_context.py
# 消息上下文，用于在管道中传递消息和相关信息

from typing import Dict, Any, Optional, List, Union
from core.bot_context import BotContext as CoreBotContext

class MessageContext:
    """消息上下文，封装消息处理过程中的所有相关信息"""
    
    def __init__(self, core_context: CoreBotContext, event: dict):
        self.core_context = core_context  # 核心Bot上下文
        self.event = event  # 原始事件数据
        self.message = event.get('message', '')  # 原始消息内容
        self.user_id = str(event.get('user_id', ''))  # 用户ID
        self.group_id = event.get('group_id')  # 群ID，私聊为None
        self.message_id = event.get('message_id')  # 消息ID
        self.message_type = event.get('message_type', '')  # 消息类型：group/private
        self.post_type = event.get('post_type', '')  # 事件类型：message/request/notice
        
        # 处理结果
        self.processed = False  # 消息是否已被处理
        self.response = None  # 处理响应
        self.handled_by = None  # 处理者标识
        
        # 扩展属性
        self.extra_data: Dict[str, Any] = {}  # 用于在不同阶段传递数据
        
        # 处理器优先级
        self.priority_handlers: List[str] = []  # 优先处理的处理器列表
        
    def is_group_message(self) -> bool:
        """判断是否为群消息"""
        return self.message_type == 'group'
    
    def is_private_message(self) -> bool:
        """判断是否为私聊消息"""
        return self.message_type == 'private'
    
    def set_processed(self, handled_by: str, response: Any = None):
        """标记消息已处理"""
        self.processed = True
        self.handled_by = handled_by
        self.response = response
    
    def add_extra_data(self, key: str, value: Any):
        """添加扩展数据"""
        self.extra_data[key] = value
    
    def get_extra_data(self, key: str, default: Any = None) -> Any:
        """获取扩展数据"""
        return self.extra_data.get(key, default)
    
    def should_continue_processing(self) -> bool:
        """判断是否应该继续处理"""
        return not self.processed
    
    def __str__(self) -> str:
        return f"MessageContext(type={self.message_type}, user={self.user_id}, group={self.group_id}, processed={self.processed})"
