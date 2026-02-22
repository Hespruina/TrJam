import asyncio
import json
import logging
from typing import Dict, Optional, Set
from aiohttp import web
import websockets
import time

from core.port_manager import port_manager
from logger_config import get_logger

logger = get_logger("WebSocketForwarder")

class WebSocketForwarder:
    """WebSocket转发器，基于OneBot协议实现双向数据转发"""
    
    def __init__(self, port: int, token: str):
        self.port = port
        self.token = token
        self.server = None
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.parent_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.running = False
        # 添加心跳监控
        self.last_ping_times: Dict[str, float] = {}
        self.ping_intervals: Dict[str, float] = {}
        self.heartbeat_timeout = 45.0  # 心跳超时时间（秒）
        self.heartbeat_task = None  # 心跳监控任务
    
    async def start(self):
        """启动WebSocket转发器"""
        try:
            # 确保handle_connection函数能够正确处理websockets库传递的所有参数
            async def handle_connection(*args, **kwargs):
                # 从参数中提取websocket对象
                websocket = args[0]
                await self._handle_connection(websocket)
            
            # 配置WebSocket服务器，设置ping间隔
            self.server = await websockets.serve(
                handle_connection,
                '127.0.0.1',
                self.port,
                ping_interval=25,  # 每25秒发送一次ping
                ping_timeout=20,   # 20秒内必须收到pong响应
                close_timeout=15   # 连接关闭超时时间
            )
            self.running = True
            
            # 启动心跳监控任务
            self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            
            logger.info(f"WebSocket转发器已启动，监听端口: {self.port}")
        except Exception as e:
            logger.error(f"启动WebSocket转发器失败: {e}")
            raise
    
    async def _heartbeat_monitor(self):
        """心跳监控任务，定期检查连接状态"""
        while self.running:
            try:
                current_time = time.time()
                disconnected_clients = []
                
                # 检查每个连接的心跳时间
                for client_id, last_ping_time in self.last_ping_times.items():
                    if current_time - last_ping_time > self.heartbeat_timeout:
                        logger.warning(f"客户端 {client_id} 心跳超时，准备断开连接")
                        disconnected_clients.append(client_id)
                
                # 断开超时的连接
                for client_id in disconnected_clients:
                    if client_id in self.connections:
                        try:
                            await self.connections[client_id].close(code=1000, reason="Heartbeat timeout")
                            logger.info(f"已断开超时连接: {client_id}")
                        except Exception as e:
                            logger.error(f"断开连接 {client_id} 时发生错误: {e}")
                        finally:
                            # 清理连接数据
                            if client_id in self.connections:
                                del self.connections[client_id]
                            if client_id in self.last_ping_times:
                                del self.last_ping_times[client_id]
                            if client_id in self.ping_intervals:
                                del self.ping_intervals[client_id]
                
                await asyncio.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                logger.error(f"心跳监控任务发生错误: {e}")
                await asyncio.sleep(5)
    
    async def send_to_subbots(self, message: str):
        """发送消息给所有子机器人"""
        disconnected_clients = []
        for client_id, conn in self.connections.items():
            try:
                await conn.send(message)
                # 更新最后发送时间作为心跳参考
                self.last_ping_times[client_id] = time.time()
            except Exception as e:
                logger.error(f"发送消息给子机器人 {client_id} 失败: {e}")
                disconnected_clients.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected_clients:
            if client_id in self.connections:
                del self.connections[client_id]
            if client_id in self.last_ping_times:
                del self.last_ping_times[client_id]
            if client_id in self.ping_intervals:
                del self.ping_intervals[client_id]
    
    async def stop(self):
        """停止WebSocket转发器"""
        self.running = False
        
        # 取消心跳监控任务
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.running and self.server:
            self.server.close()
            await self.server.wait_closed()
            self.running = False
            logger.info(f"WebSocket转发器已停止，端口: {self.port}")
        
        # 关闭所有连接
        for conn in list(self.connections.values()):
            try:
                await conn.close()
            except:
                pass
        
        for conn in list(self.parent_connections.values()):
            try:
                await conn.close()
            except:
                pass
        
        self.connections.clear()
        self.parent_connections.clear()
        self.last_ping_times.clear()
        self.ping_intervals.clear()
    
    async def _handle_connection(self, websocket):
        """处理新的WebSocket连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"新的WebSocket连接: {client_id}")
        
        try:
            # 初始化心跳监控
            self.last_ping_times[client_id] = time.time()
            self.ping_intervals[client_id] = 25.0  # 默认心跳间隔
            
            # 验证token
            if not await self._authenticate(websocket):
                logger.warning(f"连接 {client_id} 认证失败，已关闭")
                await websocket.close()
                return
            
            self.connections[client_id] = websocket
            
            # 处理消息
            async for message in websocket:
                await self._handle_message(client_id, message)
                # 更新最后活动时间
                self.last_ping_times[client_id] = time.time()
                
        except websockets.ConnectionClosed:
            logger.info(f"WebSocket连接已关闭: {client_id}")
        except Exception as e:
            logger.error(f"处理WebSocket连接时发生错误: {e}")
        finally:
            if client_id in self.connections:
                del self.connections[client_id]
            if client_id in self.last_ping_times:
                del self.last_ping_times[client_id]
            if client_id in self.ping_intervals:
                del self.ping_intervals[client_id]
    
    async def _authenticate(self, websocket):
        """验证连接的token"""
        try:
            # 等待认证消息
            message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            data = json.loads(message)
            
            if data.get('action') == 'auth' and data.get('params', {}).get('access_token') == self.token:
                # 发送认证成功响应
                await websocket.send(json.dumps({
                    'status': 'ok',
                    'retcode': 0,
                    'data': None,
                    'echo': data.get('echo')
                }))
                return True
            else:
                # 发送认证失败响应
                await websocket.send(json.dumps({
                    'status': 'failed',
                    'retcode': 401,
                    'data': None,
                    'echo': data.get('echo')
                }))
                return False
        except asyncio.TimeoutError:
            logger.warning("认证超时")
            return False
        except Exception as e:
            logger.error(f"认证过程中发生错误: {e}")
            return False
    
    async def _handle_message(self, client_id: str, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            logger.debug(f"收到消息: {data}")
            
            # 这里需要将消息转发给主机器人的消息处理系统
            # 由于主机器人不是通过WebSocket服务器接收消息的
            # 我们需要通过其他方式将消息传递给主机器人
            logger.info(f"子机器人消息: {data}")
            
            # 检查是否有消息处理回调函数
            if hasattr(self, 'message_handler'):
                try:
                    # 调用消息处理回调函数，将消息传递给主机器人
                    await self.message_handler(message)
                except Exception as e:
                    logger.error(f"调用消息处理回调函数时发生错误: {e}")
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}")
    
    def set_message_handler(self, handler):
        """设置消息处理回调函数"""
        self.message_handler = handler
    
    async def connect_to_parent(self, parent_url: str, parent_token: str) -> bool:
        """连接到主机器人"""
        try:
            websocket = await websockets.connect(parent_url)
            
            # 发送认证消息
            auth_message = json.dumps({
                'action': 'auth',
                'params': {
                    'access_token': parent_token
                },
                'echo': 'auth'
            })
            await websocket.send(auth_message)
            
            # 等待认证响应
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            data = json.loads(response)
            
            if data.get('status') == 'ok':
                parent_id = f"parent_{id(websocket)}"
                self.parent_connections[parent_id] = websocket
                logger.info(f"已成功连接到主机器人: {parent_url}")
                
                # 启动消息处理任务
                asyncio.create_task(self._handle_parent_message(parent_id, websocket))
                return True
            else:
                logger.error(f"连接主机器人认证失败: {data}")
                await websocket.close()
                return False
        except Exception as e:
            logger.error(f"连接主机器人失败: {e}")
            return False
    
    async def _handle_parent_message(self, parent_id: str, websocket):
        """处理从主机器人收到的消息"""
        try:
            async for message in websocket:
                # 转发消息到所有子机器人连接
                for conn in list(self.connections.values()):
                    try:
                        await conn.send(message)
                    except Exception as e:
                        logger.error(f"转发消息到子机器人失败: {e}")
        except websockets.ConnectionClosed:
            logger.info(f"与主机器人的连接已关闭")
            if parent_id in self.parent_connections:
                del self.parent_connections[parent_id]
        except Exception as e:
            logger.error(f"处理主机器人消息时发生错误: {e}")
            if parent_id in self.parent_connections:
                del self.parent_connections[parent_id]
    
    def is_running(self) -> bool:
        """检查转发器是否正在运行"""
        return self.running
    
    def get_port(self) -> int:
        """获取转发器的端口"""
        return self.port