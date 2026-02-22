# utils/message_sender/message_builder.py
# 消息构建器类

import json
import asyncio
from typing import Optional, Dict, Any, Callable, List
from logger_config import get_logger
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api

logger = get_logger("MessageBuilder")

class MessageBuilder:
    """消息构建器，提供链式调用接口来构建复杂消息"""
    
    def __init__(self, context: BotContext):
        self.context = context
        self.group_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.message_segments: List[Dict[str, Any]] = []
        self.callback: Optional[Callable] = None
        
        # 添加敏感词检测绕过相关属性
        self.badword_bypass = False  # 是否绕过敏感词检测
        self.bypass_reason = ""  # 绕过原因（用于审计）
        self.bypass_requested_by = ""  # 请求绕过的用户ID
        self.bypass_permission_level = 2  # 绕过所需权限级别，默认为Root权限
        
        # 添加自动撤回相关属性
        self.auto_recall_seconds: Optional[int] = None  # 自动撤回时间（秒）
    
    def set_group_id(self, group_id: str) -> 'MessageBuilder':
        """设置群ID"""
        self.group_id = group_id
        return self
    
    def set_user_id(self, user_id: str) -> 'MessageBuilder':
        """设置用户ID"""
        self.user_id = user_id
        return self
    
    def set_callback(self, callback: Callable) -> 'MessageBuilder':
        """设置消息发送成功后的回调函数"""
        self.callback = callback
        return self
    
    def add_text(self, text: str) -> 'MessageBuilder':
        """添加文本消息段"""
        if text:
            self.message_segments.append({"type": "text", "data": {"text": text}})
        return self
    
    def add_at(self, user_id: Optional[str] = None) -> 'MessageBuilder':
        """添加@消息段，默认@设置的用户"""
        target_id = user_id or self.user_id
        if target_id:
            self.message_segments.append({"type": "at", "data": {"qq": target_id}})
            # 添加一个空格，避免@后直接接正文
            self.message_segments.append({"type": "text", "data": {"text": " "}})
        return self
    
    def add_image(self, image_path: str) -> 'MessageBuilder':
        """添加图片消息段（支持本地路径或URL）"""
        # 这里简化处理，实际应该根据路径类型判断是本地文件还是URL
        self.message_segments.append({"type": "image", "data": {"file": image_path}})
        return self
    
    def add_reply(self, message_id: str) -> 'MessageBuilder':
        """添加回复消息段"""
        self.message_segments.append({"type": "reply", "data": {"id": message_id}})
        return self
    
    def set_badword_bypass(self, enabled: bool = True, reason: str = "", requested_by: str = "", permission_level: int = 2) -> 'MessageBuilder':
        """设置是否绕过敏感词检测
        
        Args:
            enabled: 是否启用绕过
            reason: 绕过原因（必填，用于审计）
            requested_by: 请求绕过的用户ID
            permission_level: 执行绕过所需的最低权限级别（默认Root权限）
        """
        self.badword_bypass = enabled
        self.bypass_reason = reason
        self.bypass_requested_by = requested_by
        self.bypass_permission_level = permission_level
        return self
    
    def set_auto_recall(self, seconds: int) -> 'MessageBuilder':
        """设置消息自动撤回时间
        
        Args:
            seconds: 自动撤回时间（秒）
        """
        if seconds > 0:
            self.auto_recall_seconds = seconds
        return self

    def get_message(self) -> List[Dict[str, Any]]:
        """获取构建好的消息段列表"""
        return self.message_segments
    
    async def send(self) -> Optional[str]:
        """直接发送构建好的消息"""
        if not self.group_id:
            logger.error("群ID未设置，无法发送消息")
            return None
        
        # 创建包含自动撤回逻辑的回调函数
        original_callback = self.callback
        
        async def enhanced_callback(message_id: str):
            # 调用原始回调函数（如果有）
            if original_callback:
                await original_callback(message_id)
            
            # 处理自动撤回
            if self.auto_recall_seconds:
                logger.info(f"消息 {message_id} 将在 {self.auto_recall_seconds} 秒后自动撤回")
                
                # 创建后台任务执行撤回
                async def recall_task():
                    try:
                        await asyncio.sleep(self.auto_recall_seconds)
                        recall_result = await call_onebot_api(
                            context=self.context,
                            action="delete_msg",
                            params={"message_id": message_id}
                        )
                        if recall_result and recall_result.get("success"):
                            logger.info(f"成功撤回消息 {message_id}")
                        else:
                            logger.error(f"撤回消息 {message_id} 失败: {recall_result}")
                    except Exception as e:
                        logger.error(f"执行自动撤回时发生错误: {e}")
                
                # 创建并启动后台任务
                asyncio.create_task(recall_task())
        
        # 使用BotContext的send_group_message方法发送消息
        # 这样可以获取真实的消息ID
        try:
            # 检查是否有绕过原因和请求用户
            bypass_reason = self.bypass_reason or ""
            bypass_requested_by = self.bypass_requested_by or ""
            
            # 发送消息并获取真实的消息ID
            # 注意：send_group_message返回的是echo，不是message_id
            # 真实的message_id会通过回调函数传递
            echo = await self.context.send_group_message(
                str(self.group_id),
                self.message_segments,
                enhanced_callback
            )
            
            logger.debug(f"消息发送成功，echo: {echo}")
            return echo
        except Exception as e:
            logger.error(f"发送消息时发生错误: {e}")
            return None