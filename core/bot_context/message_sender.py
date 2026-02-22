# core/bot_context/message_sender.py
# 消息发送功能

import asyncio
import uuid
from typing import Optional, Dict, Any, Callable, List
from logger_config import get_logger, log_exception
from utils.api_utils import call_onebot_api

logger = get_logger("BotContextMessageSender")

class MessageSender:
    """消息发送器"""
    
    def __init__(self):
        self._websocket = None
        self._lock = asyncio.Lock()
        # 用于存储消息回调函数的字典，key为echo，value为回调函数
        self._message_callbacks = {}
        # 用于存储待处理的消息ID映射，key为临时ID，value为消息内容和回调
        self._pending_messages = {}
        # 用于生成唯一的临时消息ID
        self._message_counter = 0
        # 上下文引用，用于访问多WebSocket管理器
        self._context = None

    @property
    def websocket(self):
        return self._websocket

    async def set_websocket(self, ws):
        """设置当前的WebSocket连接。"""
        async with self._lock:
            self._websocket = ws

    def set_context(self, context):
        """设置上下文引用，用于访问多WebSocket管理器"""
        self._context = context

    async def send_group_message(self, group_id: str, message: list, callback: Optional[Callable] = None) -> Optional[str]:
        """发送群消息并可选注册回调函数
        
        :param group_id: 群号
        :param message: 消息内容，格式为[{type: "text", data: {text: "消息内容"}}]
        :param callback: 消息发送成功后的回调函数，接收message_id作为参数
        :return: echo标识或None
        """
        # 使用传统的单WebSocket发送
        return await self._send_group_message_single(group_id, message, callback)
    
    async def send_private_message(self, user_id: str, message: list, callback: Optional[Callable] = None) -> Optional[str]:
        """发送私聊消息并可选注册回调函数
        
        :param user_id: 用户ID
        :param message: 消息内容，格式为[{type: "text", data: {text: "消息内容"}}]
        :param callback: 消息发送成功后的回调函数，接收message_id作为参数
        :return: echo标识或None
        """
        # 使用传统的单WebSocket发送
        return await self._send_private_message_single(user_id, message, callback)
    
    async def _send_private_message_single(self, user_id: str, message: list, callback: Optional[Callable] = None) -> Optional[str]:
        """单WebSocket模式下发送私聊消息"""
        return await self._send_message_with_retry('send_private_msg', {'user_id': user_id, 'message': message}, callback)
    
    async def _send_message_with_retry(self, action: str, api_params: dict, callback: Optional[Callable] = None) -> Optional[str]:
        """发送消息并在特定错误时重试一次"""
        # 如果提供了回调函数，则存储它
        echo = str(uuid.uuid4())
        if callback:
            self._message_callbacks[echo] = callback
            
        # 最多尝试2次（原始尝试 + 1次重试）
        for attempt in range(2):
            try:
                response = await call_onebot_api(self._context, action, api_params)
                if response and response.get('success'):
                    data = response.get('data', {})
                    # 检查响应格式
                    if isinstance(data, dict):
                        if data.get('status') == 'ok' and 'data' in data:
                            message_id = data['data'].get('message_id')
                            if message_id and callback:
                                try:
                                    await callback(message_id)
                                    logger.info(f"消息发送成功，message_id: {message_id}, echo: {echo}, 尝试次数: {attempt + 1}")
                                except Exception as e:
                                    log_exception(logger, f"执行消息回调时发生异常", e)
                            logger.debug(f"消息已发送，echo: {echo}, 尝试次数: {attempt + 1}")
                            return echo
                        elif data.get('status') == 'failed' and 'data' in data:
                            error_data = data.get('data', {})
                            # 检查是否是EventChecker Failed错误
                            error_message = data.get('message', '')
                            if 'EventChecker Failed' in error_message and attempt == 0:
                                logger.warning(f"消息发送失败，将重试一次: {error_message}")
                                # 等待一小段时间后重试
                                await asyncio.sleep(1)
                                continue
                            else:
                                logger.error(f"消息发送失败，响应格式异常: {data}")
                                if echo in self._message_callbacks:
                                    del self._message_callbacks[echo]
                                return None
                        else:
                            logger.error(f"消息发送失败，响应格式异常: {data}")
                            if echo in self._message_callbacks:
                                del self._message_callbacks[echo]
                            return None
                    else:
                        logger.error(f"消息发送失败，响应格式异常: {data}")
                        if echo in self._message_callbacks:
                            del self._message_callbacks[echo]
                        return None
                else:
                    error_msg = response.get('error', '未知错误') if response else '无响应'
                    logger.error(f"发送消息失败: {error_msg}")
                    if echo in self._message_callbacks:
                        del self._message_callbacks[echo]
                    return None
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                if attempt == 0:
                    logger.warning(f"消息发送异常，将重试一次: {e}")
                    # 等待一小段时间后重试
                    await asyncio.sleep(1)
                    continue
                else:
                    if echo in self._message_callbacks:
                        del self._message_callbacks[echo]
                    return None
    

    
    async def _send_group_message_single(self, group_id: str, message: list, callback: Optional[Callable] = None) -> Optional[str]:
        """单WebSocket模式下发送群消息"""
        return await self._send_message_with_retry('send_group_msg', {'group_id': group_id, 'message': message}, callback)
    


    def register_message_callback(self, echo: str, callback: Callable):
        """注册消息回调函数
        
        :param echo: 请求的echo标识
        :param callback: 回调函数，接收message_id作为参数
        """
        self._message_callbacks[echo] = callback

    def handle_message_response(self, response: dict):
        """处理消息响应
        
        :param response: 包含status、data和echo的响应字典
        """
        status = response.get('status')
        data = response.get('data')
        echo = response.get('echo')
        retcode = response.get('retcode', 0)
        
        # 记录收到消息反馈的调试信息
        logger.debug(f"收到消息反馈 - status: {status}, retcode: {retcode}, echo: {echo}, data: {data}")
        
        # 如果响应中包含echo，且存在对应的回调函数
        if echo and echo in self._message_callbacks:
            callback = self._message_callbacks[echo]
            if (status == 'ok' or retcode == 0) and data and 'message_id' in data:
                # 消息发送成功，执行回调
                try:
                    asyncio.create_task(callback(data['message_id']))
                    logger.info(f"消息发送成功，message_id: {data['message_id']}, echo: {echo}")
                except Exception as e:
                    log_exception(logger, f"执行消息回调时发生异常", e)
                # 执行完回调后删除
                del self._message_callbacks[echo]
            elif status == 'failed' or retcode != 0:
                error_msg = data.get('wording', '未知错误') if data else '未知错误'
                logger.error(f"消息发送失败: {error_msg}, echo: {echo}")
                # 消息发送失败，删除回调
                del self._message_callbacks[echo]