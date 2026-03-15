# core/message_router.py
# 负责接收WebSocket和HTTP消息，并将其分发给相应的处理器

import json
import asyncio
import aiohttp
from aiohttp import web
from typing import Optional
from logger_config import get_logger, log_exception, print_colored_message
from core.bot_context import BotContext
from handlers import private_handler, group_handler, request_handler, notice_handler, meta_event_handler
from handlers.http_handler import handle_http_request as process_http_request
from core.message_pipeline.pipeline_manager import PipelineManager
import os
import sys
import uuid
from utils.api_utils import call_onebot_api
from datetime import datetime

logger = get_logger("MessageRouter")

class MessageRouter:
    """消息路由器，负责将不同类型的消息分发给对应的处理器。"""

    def __init__(self, context: BotContext):
        self.context = context
        # 存储API请求的回调
        self.api_callbacks = {}
        # 存储API调用的Future对象
        self.api_calls = {}
        # 初始化消息处理管道
        self.pipeline_manager = PipelineManager(context)
        # 插件管理器（稍后在 bot.py 中初始化）
        self.plugin_manager = None
    
    async def forward_message_to_subbots(self, message: str):
        """将消息转发给所有子机器人"""
        if hasattr(self.context, 'subbot_manager'):
            subbot_manager = self.context.subbot_manager
            if hasattr(subbot_manager, 'forwarders'):
                for forwarder in subbot_manager.forwarders.values():
                    try:
                        await forwarder.send_to_subbots(message)
                    except Exception as e:
                        logger.error(f"转发消息给子机器人失败: {e}")


    
    async def handle_websocket_message(self, ws):
        """处理来自WebSocket的单条消息。"""
        
        async for msg in ws:
            try:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    # 记录非文本消息类型的debug日志
                    logger.debug(f"收到非文本WebSocket消息，类型: {msg.type}")
                    continue

                # 添加debug级别的websocket原始消息日志
                logger.debug(f"收到原始WebSocket文本消息: {msg.data}")
                
                event = json.loads(msg.data)
                logger.debug(f"收到WebSocket文本消息，事件类型: {event.get('post_type')}")
                
                # 获取当前连接对应的账号ID
                account_id = None
                if hasattr(ws, '_account_id'):
                    account_id = ws._account_id
                
                # 检查是否为 Parallel 模式
                is_parallel = False
                if hasattr(self.context, 'multi_ws_manager'):
                    multi_ws_manager = self.context.multi_ws_manager
                    is_parallel = multi_ws_manager.is_parallel_mode()
                    
                    if is_parallel:
                        # Parallel 模式下，处理所有来自已知账号的消息
                        logger.debug(f"Parallel 模式: 处理账号 {account_id} 的消息")
                        # 转发消息给子机器人
                        await self.forward_message_to_subbots(msg.data)
                    else:
                        # Fallback 模式下，只处理活跃账号的消息
                        if hasattr(multi_ws_manager, 'active_connection_id'):
                            active_conn_id = multi_ws_manager.active_connection_id
                            if account_id == active_conn_id:
                                await self.forward_message_to_subbots(msg.data)
                            else:
                                logger.debug(f"忽略非活跃账号 {account_id} 的消息")
                
                # 处理API回调
                post_type = event.get('post_type')
                
                # 优先处理消息发送反馈（包含status和data字段的消息反馈事件）
                if 'status' in event and 'data' in event:
                    await self._handle_message_feedback(event)
                    continue
                
                # 处理API回调（通过call_api方法发起的请求）
                if 'echo' in event and event.get('echo') in self.api_callbacks:
                    await self._handle_api_callback(event)
                    continue

                # 处理不同类型的消息
                if post_type == 'message':
                    message_type = event.get('message_type')
                    user_id = event.get('user_id', 'unknown')
                    raw_message = event.get('raw_message', '')
                    message_id = event.get('message_id', 'unknown')
                    
                    # 检查是否应该处理该消息（Parallel Pro 模式需要传递 account_id）
                    if not self.context.should_handle_message(event, account_id=account_id):
                        continue
                    
                    # 在事件中添加账号 ID 信息，供后续处理使用
                    if account_id is not None:
                        event['_account_id'] = account_id
                    
                    # 分发事件到插件（在处理器之前）
                    if self.plugin_manager:
                        await self.plugin_manager.dispatch_event(post_type, event)
                    
                    # 仅在日志中过滤CQ代码，不影响原始消息处理
                    def filter_cq_code_for_log(text):
                        import re
                        # 使用正则表达式移除所有CQ代码
                        return re.sub(r'\[CQ:[^\]]*\]', '', text)
                        
    
                    
                    if message_type == 'private':
                        sub_type = event.get('sub_type', 'unknown')
                        filtered_message = filter_cq_code_for_log(raw_message)
                        # 获取用户名，优先使用nickname
                        sender = event.get('sender', {})
                        username = sender.get('nickname', str(user_id))
                        # 使用彩色输出格式
                        timestamp = datetime.now().strftime('%m-%d %H:%M:%S')
                        print_colored_message(timestamp, "私信", username, filtered_message)
                        await private_handler.handle_private_message(self.context, event)
                    elif message_type == 'group':
                        group_id = event.get('group_id', 'unknown')
                        sub_type = event.get('sub_type', 'unknown')
                        filtered_message = filter_cq_code_for_log(raw_message)
                        # 获取群名，优先使用group_name
                        group_name = event.get('group_name', f"{group_id}")
                        # 获取用户名，优先使用群昵称(card)，然后是nickname，最后是user_id
                        sender = event.get('sender', {})
                        card = sender.get('card', '')
                        nickname = sender.get('nickname', '')
                        # 确保card和nickname不为空字符串
                        if card:
                            username = card
                        elif nickname:
                            username = nickname
                        else:
                            username = str(user_id)
                        # 添加debug日志，查看sender信息
                        logger.debug(f"Sender info: card='{card}', nickname='{nickname}', user_id={user_id}, username='{username}'")
                        # 使用彩色输出格式
                        timestamp = datetime.now().strftime('%m-%d %H:%M:%S')
                        print_colored_message(timestamp, group_name, username, filtered_message)
                        
                        # 检查用户是否被软禁言（Root用户不受限制）
                        from commands.softmute_command import is_user_softmuted
                        if str(user_id) != str(self.context.get_config_value("Root_user", "")) and is_user_softmuted(group_id, user_id):
                            logger.info(f"检测到软禁言用户 {user_id} 在群 {group_id} 发送消息，尝试撤回")
                            try:
                                recall_result = await call_onebot_api(self.context, 'delete_msg', {'message_id': message_id}, account_id=account_id)
                                # 检查API调用是否成功以及业务处理是否成功
                                if recall_result and recall_result.get('success') and recall_result.get('data', {}).get('status') == 'ok':
                                    logger.info(f"成功撤回软禁言用户 {user_id} 的消息")
                                else:
                                    logger.warning(f"撤回软禁言用户消息失败: {recall_result}")
                            except Exception as e:
                                logger.error(f"撤回消息时发生异常: {e}")
                        
                        # 检查用户是否在句句名言名单中且本群被信任
                        from commands.allquote_command import is_user_allquoted
                        from core.trust_manager import trust_manager
                        if is_user_allquoted(group_id, user_id) and trust_manager.is_trusted_group(str(group_id)):
                            logger.info(f"检测到句句名言用户 {user_id} 在群 {group_id} 发送消息，尝试生成名言图片")
                            try:
                                # 调用quote命令的内部处理函数
                                from commands.quote_command import handle_quote_internal
                                # 构建原始消息结构，包含引用消息
                                raw_message_with_reply = [
                                    {
                                        "type": "reply",
                                        "data": {
                                            "id": message_id
                                        }
                                    }
                                ]
                                await handle_quote_internal(self.context, user_id, group_id, raw_message_with_reply, is_configured=True)
                            except Exception as e:
                                logger.error(f"生成名言图片时发生异常: {e}")
                        
                        await group_handler.handle_group_message(self.context, event)
                elif post_type == 'request':
                    # 对于 request 事件，尝试从 self_id 获取账号 ID
                    if account_id is None:
                        self_id = event.get('self_id')
                        if self_id:
                            account = self.context.get_account_by_qq(str(self_id))
                            if account:
                                account_id = account.get('id')
                                logger.debug(f"Request 事件：从 self_id {self_id} 推断出账号 ID {account_id}")
                    
                    # 检查是否应该处理该消息（Parallel Pro 模式需要传递 account_id）
                    if not self.context.should_handle_message(event, account_id=account_id):
                        continue
                    # 在事件中添加账号 ID 信息
                    if account_id is not None:
                        event['_account_id'] = account_id
                    # 分发事件到插件
                    if self.plugin_manager:
                        await self.plugin_manager.dispatch_event(post_type, event)
                    await request_handler.handle_request_event(self.context, event)
                elif post_type == 'notice':
                    # 对于 notice 事件，尝试从 self_id 获取账号 ID
                    if account_id is None:
                        self_id = event.get('self_id')
                        if self_id:
                            account = self.context.get_account_by_qq(str(self_id))
                            if account:
                                account_id = account.get('id')
                                logger.debug(f"Notice 事件：从 self_id {self_id} 推断出账号 ID {account_id}")
                    
                    # 检查是否应该处理该消息（Parallel Pro 模式需要传递 account_id）
                    if not self.context.should_handle_message(event, account_id=account_id):
                        continue
                    # 在事件中添加账号 ID 信息
                    if account_id is not None:
                        event['_account_id'] = account_id
                    # 分发事件到插件
                    if self.plugin_manager:
                        await self.plugin_manager.dispatch_event(post_type, event)
                    await notice_handler.handle_notice_event(self.context, event)
                elif post_type == 'meta_event':
                    # 在事件中添加账号ID信息
                    if account_id is not None:
                        event['_account_id'] = account_id
                    # 分发事件到插件
                    if self.plugin_manager:
                        await self.plugin_manager.dispatch_event(post_type, event)
                    await meta_event_handler.handle_meta_event(self.context, event)
                else:
                    logger.debug(f"忽略未知事件类型: {post_type}")

            except Exception as e:
                log_exception(logger, f"消息处理异常", e)

    async def _handle_message_feedback(self, event: dict):
        """处理消息发送反馈
        
        当消息发送成功后，WebSocket会收到一个包含status='ok'和message_id的反馈
        此方法将处理这些反馈，更新消息状态并触发相应的回调
        """
        try:
            # 调用BotContext中的处理方法
            self.context.handle_message_response(event)
        except Exception as e:
            log_exception(logger, f"处理消息反馈时发生异常", e)

    async def _handle_api_callback(self, event: dict):
        """处理API回调"""
        echo = event.get('echo')
        if echo in self.api_callbacks:
            future = self.api_callbacks.pop(echo)
            future.set_result(event)

    async def handle_http_request(self, request: web.Request) -> web.Response:
        """处理HTTP请求。"""
        return await process_http_request(self.context, request)

    async def call_api(self, action: str, params: dict, account_id: int = None) -> dict:
        """调用OneBot API并返回结果
        
        Args:
            action: API动作
            params: 参数
            account_id: 指定账号ID（parallel模式下使用），None则使用当前活跃账号
        """
        echo = str(uuid.uuid4())
        payload = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        # 创建Future对象用于等待回调
        future = asyncio.Future()
        self.api_callbacks[echo] = future
        
        try:
            # 确定使用哪个WebSocket连接
            websocket = None
            if account_id is not None and hasattr(self.context, 'multi_ws_manager'):
                # Parallel 模式下使用指定账号的连接
                conn = self.context.multi_ws_manager.get_connection_by_id(account_id)
                if conn and conn.websocket and not conn.websocket.closed:
                    websocket = conn.websocket
                    logger.debug(f"使用账号 {account_id} 的连接发送API请求")
            
            # 如果没有指定账号或指定账号不可用，使用默认连接
            if websocket is None:
                websocket = self.context.websocket
                if account_id is not None:
                    logger.warning(f"账号 {account_id} 的连接不可用，使用默认连接")
            
            # 发送API请求
            if websocket and not websocket.closed:
                await websocket.send_json(payload)
                # 等待回调结果，设置超时时间
                result = await asyncio.wait_for(future, timeout=30.0)
                return result
            else:
                logger.error("WebSocket连接已关闭，无法发送API请求")
                return {"status": "failed", "retcode": -1, "data": None}
        except asyncio.TimeoutError:
            logger.error(f"API调用超时: {action}")
            return {"status": "failed", "retcode": -2, "data": None}
        except Exception as e:
            logger.error(f"API调用异常: {e}")
            return {"status": "failed", "retcode": -3, "data": None}

    async def get_member_info(self, group_id, user_id):
        """获取群成员信息"""
        try:
            result = await self.call_api("get_group_member_info", {
                "group_id": group_id,
                "user_id": user_id
            })
            return result.get("data") if result.get("status") == "ok" else None
        except Exception as e:
            logger.error(f"获取群成员信息失败: {e}")
            return None

    async def get_group_info(self, group_id):
        """获取群信息"""
        try:
            result = await self.call_api("get_group_info", {
                "group_id": group_id
            })
            return result.get("data") if result.get("status") == "ok" else None
        except Exception as e:
            logger.error(f"获取群信息失败: {e}")
            return None

    async def get_image_base64(self, url):
        """获取图片的base64编码"""
        # 这里应该实现图片下载和转base64的逻辑
        # 暂时返回None，后续需要实现具体逻辑
        logger.warning("get_image_base64功能尚未实现")
        return None

    async def get_record_detail(self, file):
        """获取语音详情"""
        try:
            result = await self.call_api("get_record", {
                "file": file
            })
            return result.get("data") if result.get("status") == "ok" else None
        except Exception as e:
            logger.error(f"获取语音详情失败: {e}")
            return None

    async def get_self_info(self):
        """获取机器人自身信息"""
        try:
            result = await self.call_api("get_login_info", {})
            return result.get("data") if result.get("status") == "ok" else None
        except Exception as e:
            logger.error(f"获取自身信息失败: {e}")
            return None

    async def get_message_detail(self, message_id):
        """获取消息详情"""
        # 已移除对get_message_storage的引用
        logger.warning("get_message_detail功能尚未实现")
        return None
