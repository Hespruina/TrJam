# core/websocket_manager.py
# 负责管理WebSocket连接的生命周期，包括重连

import asyncio
import aiohttp
from logger_config import get_logger, log_exception
from typing import Callable, Awaitable

logger = get_logger("WebSocketManager")

class WebSocketManager:
    """管理与OneBot服务的WebSocket连接。"""

    def __init__(self, context):
        self.context = context
        self._is_running = True
        logger.debug("WebSocketManager已初始化")

    async def start_main_loop(self, message_handler: Callable[[aiohttp.ClientWebSocketResponse], Awaitable[None]]):
        """启动WebSocket主循环，包含自动重连逻辑。"""
        retry_count = 0
        
        # 从配置中获取WebSocket相关参数
        websocket_config = self.context.get_config_value('websocket', {})
        MAX_RETRIES = websocket_config.get('max_retries', 10)
        RETRY_DELAY_BASE = websocket_config.get('retry_delay_base', 5)
        RETRY_DELAY_MAX = websocket_config.get('retry_delay_max', 60)
        RETRY_BACKOFF_FACTOR = websocket_config.get('retry_backoff_factor', 2)
        HEARTBEAT_INTERVAL = websocket_config.get('heartbeat_interval', 30)

        logger.debug(f"WebSocket主循环启动，最大重试次数: {MAX_RETRIES}")
        
        while self._is_running:
            try:
                headers = {
                    "Authorization": f"Bearer {self.context.get_config_value('access_token')}",
                    "User-Agent": "PythonWebSocketClient/1.0"
                }
                
                logger.debug(f"准备创建WebSocket会话，headers: {headers}")

                async with aiohttp.ClientSession() as session:
                    ws_uri = self.context.get_config_value('ws_uri')
                    logger.debug(f"创建WebSocket会话，连接到: {ws_uri}")
                    
                    # 添加debug日志记录连接参数
                    logger.debug(f"WebSocket连接参数 - URI: {ws_uri}, 心跳间隔: {HEARTBEAT_INTERVAL}秒")
                    
                    # 准备WebSocket连接参数
                    ws_connect_params = {
                        "url": ws_uri,
                        "headers": headers
                    }
                    
                    # 只有当心跳间隔大于0时才设置心跳参数
                    if HEARTBEAT_INTERVAL > 0:
                        ws_connect_params["heartbeat"] = HEARTBEAT_INTERVAL
                    
                    async with session.ws_connect(**ws_connect_params) as ws:
                        # 设置当前WebSocket
                        await self.context.set_websocket(ws)
                        logger.info("WebSocket连接成功")
                        logger.debug(f"WebSocket连接成功，WebSocket对象ID: {id(ws)}")
                        
                        retry_count = 0 # 重置重试计数器
                        logger.debug("WebSocket主循环: 开始调用消息处理器")
                        await message_handler(ws)
                        logger.debug("WebSocket主循环: 消息处理器调用结束")

            except Exception as e:
                retry_count += 1
                logger.debug(f"WebSocket连接异常，异常类型: {type(e).__name__}")
                
                if retry_count > MAX_RETRIES:
                    logger.critical(f"WebSocket连接失败超过{MAX_RETRIES}次，程序退出。")
                    break

                # 使用配置的重试参数计算延迟时间
                delay = min(RETRY_DELAY_MAX, RETRY_DELAY_BASE * (RETRY_BACKOFF_FACTOR ** retry_count))
                log_exception(logger, f"WebSocket连接错误，{delay}秒后重试... (第{retry_count}次)", e)
                logger.debug(f"WebSocket连接重试计划 - 当前重试次数: {retry_count}, 等待时间: {delay}秒")
                await asyncio.sleep(delay)

    def stop(self):
        """停止主循环。"""
        logger.debug("WebSocketManager停止主循环")
        self._is_running = False