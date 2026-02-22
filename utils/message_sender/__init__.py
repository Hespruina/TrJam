# utils/message_sender/__init__.py
# 提供统一的消息发送和构建接口，替代原有的response_builder

import json
import time
from typing import Optional, Dict, Any, Callable, List, Union
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from core.sensitive_word_manager import is_sensitive, log_sensitive_trigger

from utils.message_sender.message_builder import MessageBuilder
from utils.message_sender.command_response import CommandResponse
from utils.message_sender.message_sender_core import send_private_message, send_group_message, process_command_response

__all__ = [
    'MessageBuilder',
    'CommandResponse',
    'send_private_message',
    'send_group_message',
    'process_command_response'
]

logger = get_logger("MessageSender")

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
    def builder(cls, builder: MessageBuilder) -> 'CommandResponse':
        """创建一个基于MessageBuilder的响应"""
        return cls("builder", builder)
    
    @classmethod
    def raw(cls, message: List[Dict[str, Any]]) -> 'CommandResponse':
        """创建一个原始消息段响应"""
        return cls("raw", message)

async def send_private_message(
    context: BotContext,
    user_id: str,
    message: Union[str, List[Dict[str, Any]]],
    callback: Optional[Callable] = None,
    badword_bypass: bool = False,  # 新增敏感词绕过高阶参数
    bypass_reason: str = "",
    bypass_request_user: str = "",
    bypass_permission_level: str = "default"
) -> Optional[str]:
    """发送私聊消息的统一接口
    
    Args:
        context: Bot上下文
        user_id: 用户ID
        message: 消息内容，可以是字符串或消息段列表
        callback: 消息发送成功后的回调函数，接收message_id作为参数
        badword_bypass: 是否启用敏感词绕过高阶
        bypass_reason: 绕过高阶原因
        bypass_request_user: 请求绕过高阶的用户
        bypass_permission_level: 权限级别
    
    Returns:
        echo标识或None
    """
    # 移除对context.websocket的直接检查，因为在parallel模式下，
    # websocket可能不存在或者已关闭，但我们仍然可以通过其他方式发送消息
    
    # 转换字符串消息为消息段
    if isinstance(message, str):
        message_segments = [{"type": "text", "data": {"text": message}}]
    else:
        message_segments = message
    
    # 检查私聊消息中的敏感词（仅对非Root用户检查，且不是绕过高阶时）
    root_user_id = str(context.get_config_value("Root_user", ""))
    if user_id != root_user_id and not badword_bypass:
        # 提取文本内容进行敏感词检查
        text_content = ""
        for segment in message_segments:
            if segment.get("type") == "text":
                text_content += segment.get("data", {}).get("text", "")
        
        contains_sensitive, sensitive_word, sensitive_reason = is_sensitive(text_content)
        if contains_sensitive:
            logger.warning(f"尝试向用户 {user_id} 发送包含敏感词 '{sensitive_word}' 的私聊消息，已阻止")
            # 向Root用户报告
            # 使用MessageBuilder构建报告消息
            builder = MessageBuilder(context)
            builder.set_user_id(root_user_id)
            builder.add_text(f"【敏感内容拦截】\n尝试向用户 {user_id} 发送包含敏感词 '{sensitive_word}' 的私聊消息，已阻止。\n内容：{text_content}")
            builder.set_badword_bypass(True, "管理员敏感词报告", "system")  # 启用绕过高阶
            await builder.send()
            # 始终回复拦截消息，但确保拦截消息不会再次触发敏感词检测
            intercept_message = "回复消息已被消息发送模块拦截。"
            if text_content != intercept_message:  # 防止死循环
                # 使用MessageBuilder发送拦截消息
                builder = MessageBuilder(context)
                builder.set_user_id(user_id)
                builder.add_text(intercept_message)
                await builder.send()
            return None
    
    # 如果启用了绕过高阶，记录日志
    if badword_bypass:
        logger.info(f"消息发送成功(敏感词绕过高阶): 用户{user_id}, 原因:{bypass_reason}, 请求用户:{bypass_request_user}")
    
    # 使用context的方法发送私聊消息，在parallel模式下会自动选择合适的账号
    return await context.send_private_message(user_id, message_segments, callback)

async def send_group_message(
    context: BotContext,
    group_id: str,
    message: Union[str, List[Dict[str, Any]]],
    callback: Optional[Callable] = None,
    badword_bypass: bool = False,  # 新增敏感词绕过高阶参数
    bypass_reason: str = "",
    bypass_request_user: str = "",
    bypass_permission_level: str = "default"
) -> Optional[str]:
    """发送群消息的统一接口
    
    Args:
        context: Bot上下文
        group_id: 群ID
        message: 消息内容，可以是字符串或消息段列表
        callback: 消息发送成功后的回调函数，接收message_id作为参数
        badword_bypass: 是否启用敏感词绕过高阶
        bypass_reason: 绕过高阶原因
        bypass_request_user: 请求绕过高阶的用户
        bypass_permission_level: 权限级别
    
    Returns:
        echo标识或None
    """
    # 转换字符串消息为消息段
    if isinstance(message, str):
        message_segments = [{"type": "text", "data": {"text": message}}]
    else:
        message_segments = message
    
    # 提取文本内容进行敏感词检查
    text_content = ""
    for segment in message_segments:
        if segment.get("type") == "text":
            text_content += segment.get("data", {}).get("text", "")
    
    # 获取report_group_id用于后续比较
    report_group_id = context.get_config_value("report_group")
    
    # 只有不是发送给report_group的消息才进行敏感词检测，且不是绕过高阶时
    contains_sensitive = False
    sensitive_word = ""
    sensitive_reason = ""
    
    if str(group_id) != str(report_group_id) and not badword_bypass:
        contains_sensitive, sensitive_word, sensitive_reason = is_sensitive(text_content)
    
    if contains_sensitive:
        logger.warning(f"尝试向群 {group_id} 发送包含敏感词 '{sensitive_word}' 的消息，已阻止")
        # 向Root用户报告（除非是私聊）
        if report_group_id:
            timestamp = int(time.time())
            formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            # 使用MessageBuilder构建报告消息
            builder = MessageBuilder(context)
            builder.set_group_id(str(report_group_id))
            builder.add_text("【敏感内容拦截】")
            builder.add_text(f"\n时间: {formatted_time}")
            builder.add_text(f"\n群号: {group_id}")
            builder.add_text(f"\n敏感词: {sensitive_word}")
            builder.add_text(f"\n内容: {text_content}")
            builder.set_badword_bypass(True, "管理员敏感词报告", "system")  # 启用绕过高阶
            await builder.send()
        # 始终回复拦截消息，但确保拦截消息不会再次触发敏感词检测
        intercept_message = "回复消息已被消息发送模块拦截。"
        if text_content != intercept_message:  # 防止死循环
            message_segments = [{"type": "text", "data": {"text": intercept_message}}]
            await context.send_group_message(group_id, message_segments)
        return None
    
    # 如果启用了绕过高阶，记录日志
    if badword_bypass:
        logger.info(f"消息发送成功(敏感词绕过高阶): 群{group_id}, 原因:{bypass_reason}, 请求用户:{bypass_request_user}")
    
    # 调用BotContext中的方法发送消息
    return await context.send_group_message(group_id, message_segments, callback)

async def process_command_response(
    context: BotContext,
    response: Union[str, CommandResponse, None],
    group_id: str,
    user_id: str
) -> Optional[str]:
    """处理命令响应并发送消息
    
    Args:
        context: Bot上下文
        response: 命令返回的响应
        group_id: 群ID
        user_id: 用户ID
    
    Returns:
        echo标识或None
    """
    if response is None:
        return None
    
    try:
        # 处理字符串响应
        if isinstance(response, str):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(response)
            return await builder.send()
        
        # 处理CommandResponse对象
        elif isinstance(response, CommandResponse):
            if response.type == "none":
                return None
            
            elif response.type == "text":
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text(response.data)
                return await builder.send()
            
            elif response.type == "builder" and isinstance(response.data, MessageBuilder):
                # 确保设置了必要的ID
                builder = response.data
                if not builder.group_id:
                    builder.set_group_id(group_id)
                if not builder.user_id:
                    builder.set_user_id(user_id)
                return await builder.send()
            
            elif response.type == "raw":
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                # 将原始消息段添加到builder中
                for segment in response.data:
                    if segment["type"] == "text":
                        builder.add_text(segment["data"]["text"])
                    elif segment["type"] == "at":
                        builder.add_at(segment["data"]["qq"])
                    elif segment["type"] == "image":
                        builder.add_image(segment["data"]["file"])
                    # 可以根据需要添加更多类型
                return await builder.send()
            
        logger.error(f"未知的响应类型: {type(response)}")
        return None
        
    except Exception as e:
        log_exception(logger, "处理命令响应时发生异常", e)
        return None