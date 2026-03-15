# core/multi_websocket_manager.py
# 负责管理多个WebSocket连接的生命周期，包括重连和故障转移

import asyncio
import aiohttp
from logger_config import get_logger, log_exception
from typing import Callable, Awaitable, Dict, List, Optional
import time

logger = get_logger("MultiWebSocketManager")

class AccountConnection:
    """表示单个账号的连接信息"""
    
    def __init__(self, account_config: dict):
        self.id = account_config.get('id')
        self.priority = account_config.get('priority', 999)
        self.ws_uri = account_config.get('ws_uri')
        self.access_token = account_config.get('access_token')
        self.websocket_config = account_config.get('websocket', {})
        self.onebot_api_base = account_config.get('onebot_api_base')
        self.onebot_access_token = account_config.get('onebot_access_token')
        self.bot_qq = account_config.get('bot_qq')
        
        # 连接状态
        self.websocket = None
        self.is_connected = False
        self.is_healthy = True  # 基于心跳的健康状态
        self.last_heartbeat_time = time.time()  # 初始化为当前时间
        # 从配置中获取心跳间隔，默认为30秒（OneBot常见默认值）
        self.heartbeat_interval = self.websocket_config.get('heartbeat_interval', 30)
        
        # 重试相关
        self.retry_count = 0
        self.max_retries = self.websocket_config.get('max_retries', 10)
        self.retry_delay_base = self.websocket_config.get('retry_delay_base', 5)
        self.retry_delay_max = self.websocket_config.get('retry_delay_max', 60)
        self.retry_backoff_factor = self.websocket_config.get('retry_backoff_factor', 2)
        
        # 静默状态
        self.is_silent = False

class MultiWebSocketManager:
    """管理多个账号的WebSocket连接。"""

    def __init__(self, context):
        self.context = context
        self._is_running = True
        self.connections: Dict[int, AccountConnection] = {}
        self.active_connection_id: Optional[int] = None
        self._lock = asyncio.Lock()
        self._connection_success_callback = None
        self._callback_executed = False  # 添加回调执行状态跟踪
        self.mode = 'fallback'  # 运行模式: 'fallback', 'parallel' 或 'parallel-pro'
        
        # Parallel Pro 模式专用：群列表缓存
        self._group_list_cache: Dict[int, List[dict]] = {}  # account_id -> group_list
        self._group_accounts_map: Dict[str, List[int]] = {}  # group_id -> [account_ids]
        self._group_list_task = None
        
        logger.debug("MultiWebSocketManager已初始化")
    
    def set_connection_success_callback(self, callback):
        """设置连接成功回调函数"""
        self._connection_success_callback = callback

    def initialize_connections(self):
        """根据配置初始化所有连接"""
        accounts_config = self.context.get_config_value('accounts', [])
        logger.info(f"从配置中加载了 {len(accounts_config)} 个账号")
        
        # 读取运行模式配置
        self.mode = self.context.get_config_value('mode', 'fallback')
        logger.info(f"运行模式: {self.mode}")
        
        for index, account_config in enumerate(accounts_config):
            logger.debug(f"处理账号配置 #{index}: {account_config}")
            # 如果没有id字段，使用索引作为默认id
            if 'id' not in account_config:
                account_config['id'] = index + 1  # 从1开始计数
                logger.debug(f"为账号 #{index} 分配默认ID: {account_config['id']}")
            
    
            
            conn = AccountConnection(account_config)
            logger.debug(f"创建账号连接对象: ID={conn.id}, Priority={conn.priority}, WS_URI={conn.ws_uri}")
            
            # 确保id是整数
            try:
                conn_id = int(conn.id)
                self.connections[conn_id] = conn
                logger.info(f"初始化账号连接: ID={conn_id}, Priority={conn.priority}")
            except (ValueError, TypeError):
                logger.error(f"账号ID '{conn.id}' 无效，跳过该账号")
        
        logger.info(f"成功初始化 {len(self.connections)} 个账号连接")
        
        # 根据模式设置活跃连接
        if self.mode in ('parallel', 'parallel-pro'):
            # Parallel 和 Parallel Pro 模式下所有账号都是活跃的
            logger.info(f"{self.mode} 模式: 所有账号将同时保持活跃")
            if self.connections:
                self.active_connection_id = min(self.connections.keys())
        else:
            # Fallback 模式下设置初始活跃连接为优先级最高的账号
            self._set_initial_active_connection()
        
        # 初始化所有连接的心跳时间为当前时间，避免首次检查时出现超大时间差
        current_time = time.time()
        for conn in self.connections.values():
            conn.last_heartbeat_time = current_time

    def _set_initial_active_connection(self):
        """设置初始活跃连接"""
        if not self.connections:
            return
            
        # 找到优先级最高的连接（数字最小）
        sorted_connections = sorted(self.connections.values(), key=lambda x: x.priority)
        self.active_connection_id = sorted_connections[0].id
        logger.info(f"设置初始活跃连接: ID={self.active_connection_id}")

    async def start_main_loop(self, message_handler: Callable[[aiohttp.ClientWebSocketResponse], Awaitable[None]]):
        """启动所有WebSocket连接的主循环"""
        # 初始化所有连接
        self.initialize_connections()
        
        if not self.connections:
            logger.error("没有配置任何账号连接")
            return
            
        # 为每个连接启动独立的任务
        tasks = []
        for conn in self.connections.values():
            # 传递连接信息给_message_handler包装函数
            async def wrapped_message_handler(ws):
                # 保存当前连接信息，以便消息处理器使用
                await message_handler(ws)
            
            task = asyncio.create_task(self._connection_loop(conn, wrapped_message_handler))
            tasks.append(task)
            
        # 启动连接监控任务
        monitor_task = asyncio.create_task(self._monitor_connections())
        tasks.append(monitor_task)
        
        # Parallel Pro 模式下启动群列表更新任务
        if self.mode == 'parallel-pro':
            self._group_list_task = asyncio.create_task(self._update_group_list_loop())
            tasks.append(self._group_list_task)
            logger.info("Parallel Pro 模式: 已启动群列表更新任务")
        
        logger.debug(f"已启动 {len(tasks)} 个连接任务")
        
        try:
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"主循环发生异常: {e}")
        finally:
            # 取消所有任务
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def _connection_loop(self, conn: AccountConnection, message_handler: Callable[[aiohttp.ClientWebSocketResponse], Awaitable[None]]):
        """单个连接的主循环"""
        logger.debug(f"启动账号 {conn.id} 的连接循环")
        
        while self._is_running:
            try:
                headers = {
                    "Authorization": f"Bearer {conn.access_token}",
                    "User-Agent": "PythonWebSocketClient/1.0"
                }
                
                logger.debug(f"账号 {conn.id}: 准备创建WebSocket会话")

                async with aiohttp.ClientSession() as session:
                    logger.debug(f"账号 {conn.id}: 创建WebSocket会话，连接到: {conn.ws_uri}")
                    
                    # 准备WebSocket连接参数
                    ws_connect_params = {
                        "url": conn.ws_uri,
                        "headers": headers
                    }
                    
                    # 只有当心跳间隔大于0时才设置心跳参数
                    if conn.heartbeat_interval > 0:
                        ws_connect_params["heartbeat"] = conn.heartbeat_interval
                    
                    async with session.ws_connect(**ws_connect_params) as ws:
                        # 更新连接状态
                        conn.websocket = ws
                        conn.is_connected = True
                        conn.retry_count = 0  # 重置重试计数器
                        conn.is_healthy = True  # 连接成功，标记为健康
                        conn.is_silent = False  # 连接成功，清除静默状态
                        
                        # 为WebSocket连接添加账号ID属性，以便在消息处理时获取
                        ws._account_id = conn.id
                        
                        # 更新上下文的websocket
                        async with self._lock:
                            if self.mode in ('parallel', 'parallel-pro'):
                                # Parallel 和 Parallel Pro 模式下，每个连接都独立处理消息
                                logger.info(f"账号 {conn.id} 在 {self.mode} 模式下连接成功")
                                # 第一个连接的回调用于启动子机器人管理器
                                if not self._callback_executed and self._connection_success_callback:
                                    logger.info(f"{self.mode} 模式: 准备执行连接成功回调")
                                    try:
                                        await self._connection_success_callback()
                                        self._callback_executed = True
                                        logger.info("连接成功回调执行完成")
                                    except Exception as e:
                                        logger.error(f"执行连接成功回调时发生错误: {e}", exc_info=True)
                            elif conn.id == self.active_connection_id:
                                logger.info(f"账号 {conn.id} 是活跃连接 (active_id: {self.active_connection_id})")
                                # 只更新活跃连接的上下文
                                await self.context.set_websocket(ws)
                                logger.info(f"账号 {conn.id} 成为活跃连接")
                                
                                # 调用连接成功回调函数，启动子机器人管理器
                                logger.info(f"检查连接成功回调: {self._connection_success_callback}")
                                logger.info(f"回调执行状态: {self._callback_executed}")
                                if self._connection_success_callback and not self._callback_executed:
                                    logger.info("准备执行连接成功回调")
                                    try:
                                        await self._connection_success_callback()
                                        self._callback_executed = True
                                        logger.info("连接成功回调执行完成")
                                    except Exception as e:
                                        logger.error(f"执行连接成功回调时发生错误: {e}", exc_info=True)
                                elif self._callback_executed:
                                    logger.info("连接成功回调已执行过，跳过")
                                else:
                                    logger.warning("连接成功回调未设置")
                            else:
                                logger.info(f"账号 {conn.id} 不是活跃连接 (active_id: {self.active_connection_id})")
                        
                        logger.info(f"账号 {conn.id} WebSocket连接成功")
                        await message_handler(ws)

            except Exception as e:
                conn.retry_count += 1
                conn.is_connected = False
                logger.debug(f"账号 {conn.id} WebSocket连接异常，异常类型: {type(e).__name__}")
                
                if conn.retry_count > conn.max_retries:
                    if not conn.is_silent:
                        logger.error(f"账号 {conn.id} WebSocket连接失败超过{conn.max_retries}次，进入静默模式")
                        conn.is_silent = True
                    conn.is_healthy = False
                    delay = conn.retry_delay_max
                else:
                    delay = min(conn.retry_delay_max, conn.retry_delay_base * (conn.retry_backoff_factor ** conn.retry_count))
                    log_exception(logger, f"账号 {conn.id} WebSocket连接错误，{delay}秒后重试... (第{conn.retry_count}次)", e)
                
                await asyncio.sleep(delay)



    async def _monitor_connections(self):
        """监控所有连接的状态并执行故障转移"""
        logger.debug("启动连接监控任务")
        while self._is_running:
            try:
                await asyncio.sleep(5)  # 每5秒检查一次
                # Parallel 模式下不需要故障转移，只监控心跳
                if self.mode == 'parallel':
                    await self._check_connections_health()
                else:
                    await self._check_and_transfer()
            except Exception as e:
                logger.error(f"连接监控任务异常: {e}")
    
    async def _check_connections_health(self):
        """Parallel 模式下检查所有连接的健康状态（仅监控，不切换）"""
        current_time = time.time()
        for conn in self.connections.values():
            if conn.is_connected:
                time_since_last_heartbeat = current_time - conn.last_heartbeat_time
                expected_heartbeat_interval = conn.heartbeat_interval
                
                # 安全检查
                if time_since_last_heartbeat < 0 or time_since_last_heartbeat > 86400:
                    logger.warning(f"账号 {conn.id} 心跳时间异常，重置为当前时间")
                    conn.last_heartbeat_time = current_time
                    time_since_last_heartbeat = 0
                
                # 检查是否超时
                if time_since_last_heartbeat > expected_heartbeat_interval * 3:
                    conn.is_healthy = False
                    logger.warning(f"账号 {conn.id} 心跳超时({time_since_last_heartbeat:.1f}秒)，标记为不健康")
                else:
                    conn.is_healthy = True
                    logger.debug(f"账号 {conn.id} 心跳正常({time_since_last_heartbeat:.1f}秒)")

    async def _check_and_transfer(self):
        """检查连接状态并执行必要的故障转移"""
        async with self._lock:
            if not self.active_connection_id:
                return
                
            active_conn = self.connections.get(self.active_connection_id)
            if not active_conn:
                return
                
            # 检查活跃连接是否健康（基于心跳）
            current_time = time.time()
            if active_conn.is_connected:
                # 如果超过两倍心跳间隔没有收到心跳，则认为连接不健康
                # 但我们也要考虑到MetaEventHandler可能已经更新了状态
                time_since_last_heartbeat = current_time - active_conn.last_heartbeat_time
                
                # 添加额外的安全检查，防止异常的时间值
                if time_since_last_heartbeat < 0 or time_since_last_heartbeat > 86400:  # 一天的秒数
                    logger.warning(f"账号 {active_conn.id} 心跳时间异常: {time_since_last_heartbeat:.1f}秒，重置为当前时间")
                    active_conn.last_heartbeat_time = current_time
                    time_since_last_heartbeat = 0
                
                # 使用实际的心跳间隔而不是配置值
                expected_heartbeat_interval = active_conn.heartbeat_interval
                logger.debug(f"账号 {active_conn.id} 心跳检查 - 距离上次心跳: {time_since_last_heartbeat:.1f}秒, 期望间隔: {expected_heartbeat_interval:.1f}秒")
                
                if time_since_last_heartbeat > expected_heartbeat_interval * 2:
                    # 只有当连接确实超时并且不是刚刚更新过状态时才标记为不健康
                    # 添加一个缓冲时间避免竞争条件，但这个缓冲时间应该与实际的心跳间隔相关
                    buffer_time = min(expected_heartbeat_interval * 0.5, 2.0)  # 最多2秒或心跳间隔的一半
                    if time_since_last_heartbeat > expected_heartbeat_interval * 2 + buffer_time:
                        active_conn.is_healthy = False
                        logger.warning(f"账号 {active_conn.id} 心跳超时({time_since_last_heartbeat:.1f}秒)，标记为不健康")
                    else:
                        logger.debug(f"账号 {active_conn.id} 心跳接近超时({time_since_last_heartbeat:.1f}秒)，等待确认")
                else:
                    logger.debug(f"账号 {active_conn.id} 心跳正常({time_since_last_heartbeat:.1f}秒)")
            
            # 执行故障转移逻辑
            # 如果活跃连接不健康，寻找替代连接
            if not active_conn.is_healthy or not active_conn.is_connected:
                logger.info(f"活跃账号 {active_conn.id} 不健康，寻找替代连接")
                await self._switch_to_best_connection()
            else:
                # 检查是否有更高优先级的健康连接可用，如果有则切换回去
                await self._switch_to_higher_priority_if_available()

    async def _switch_to_best_connection(self):
        """切换到最佳的健康连接"""
        # 寻找优先级最高且健康的连接
        healthy_connections = [
            conn for conn in self.connections.values() 
            if conn.is_connected and conn.is_healthy and conn.websocket and not conn.websocket.closed
        ]
        
        logger.debug(f"健康连接检查: 共找到 {len(healthy_connections)} 个健康连接")
        for conn in self.connections.values():
            logger.debug(f"账号 {conn.id} 状态 - 连接: {conn.is_connected}, 健康: {conn.is_healthy}, WebSocket有效: {conn.websocket and not conn.websocket.closed}")
        
        if not healthy_connections:
            logger.warning("没有找到健康的连接")
            return
            
        # 按优先级排序（数字小的优先）
        healthy_connections.sort(key=lambda x: x.priority)
        best_connection = healthy_connections[0]
        
        # 如果最佳连接不是当前活跃连接，则切换
        if best_connection.id != self.active_connection_id:
            logger.info(f"切换活跃连接从 {self.active_connection_id} 到 {best_connection.id}")
            self.active_connection_id = best_connection.id
            
            # 更新上下文中的WebSocket连接
            await self.context.set_websocket(best_connection.websocket)
            
            # 通知上下文账号变更
            await self.context.set_active_account({
                'id': best_connection.id,
                'bot_qq': best_connection.bot_qq,
                'onebot_api_base': best_connection.onebot_api_base,
                'onebot_access_token': best_connection.onebot_access_token
            })
            
            # 如果回调还未执行，且有回调函数，则执行回调
            logger.info(f"切换后检查回调执行状态: callback={self._connection_success_callback}, executed={self._callback_executed}")
            if self._connection_success_callback and not self._callback_executed:
                logger.info("切换活跃连接后执行连接成功回调")
                try:
                    await self._connection_success_callback()
                    self._callback_executed = True
                    logger.info("切换活跃连接后的回调执行完成")
                except Exception as e:
                    logger.error(f"切换活跃连接后执行回调时发生错误: {e}", exc_info=True)
            elif self._callback_executed:
                logger.info("回调已执行过，无需重复执行")
        else:
            logger.debug(f"当前活跃连接 {self.active_connection_id} 仍然是最佳选择")

    async def _switch_to_higher_priority_if_available(self):
        """如果存在更高优先级的健康连接，则切换回去"""
        active_conn = self.connections.get(self.active_connection_id)
        if not active_conn:
            return
            
        # 查找所有比当前连接优先级更高的健康连接
        higher_priority_connections = [
            conn for conn in self.connections.values()
            if conn.priority < active_conn.priority  # 优先级数字更小
            and conn.is_connected 
            and conn.is_healthy 
            and conn.websocket 
            and not conn.websocket.closed
        ]
        
        if not higher_priority_connections:
            # 没有更高优先级的连接可用
            return
            
        # 按优先级排序，选择最高优先级的连接
        higher_priority_connections.sort(key=lambda x: x.priority)
        best_connection = higher_priority_connections[0]
        
        # 切换到更高优先级的连接
        logger.info(f"发现更高优先级的连接 {best_connection.id} 可用，从 {self.active_connection_id} 切换回去")
        self.active_connection_id = best_connection.id
        
        # 更新上下文中的WebSocket连接
        await self.context.set_websocket(best_connection.websocket)
        
        # 通知上下文账号变更
        await self.context.set_active_account({
            'id': best_connection.id,
            'bot_qq': best_connection.bot_qq,
            'onebot_api_base': best_connection.onebot_api_base,
            'onebot_access_token': best_connection.onebot_access_token
        })

    def update_heartbeat(self, self_id: str, status: dict):
        """更新指定账号的心跳状态"""
        current_time = time.time()
        logger.debug(f"MultiWebSocketManager收到账号 {self_id} 的心跳更新")
        # 根据self_id找到对应的连接
        for conn in self.connections.values():
            if conn.bot_qq == str(self_id):
                prev_healthy = conn.is_healthy
                prev_interval = conn.heartbeat_interval
                if status.get('good', False) and status.get('online', False):
                    conn.last_heartbeat_time = current_time
                    conn.is_healthy = True
                    # 如果状态中有interval信息，更新心跳间隔
                    if 'interval' in status:
                        # interval是以毫秒为单位的
                        new_interval = status['interval'] / 1000
                        if new_interval != conn.heartbeat_interval:
                            logger.info(f"账号 {conn.id} 心跳间隔更新: {conn.heartbeat_interval:.1f} -> {new_interval:.1f}秒")
                        conn.heartbeat_interval = new_interval
                    if not prev_healthy:
                        logger.info(f"账号 {conn.id} 心跳恢复正常")
                    else:
                        logger.debug(f"账号 {conn.id} 心跳正常，间隔: {conn.heartbeat_interval:.1f}秒")
                else:
                    conn.is_healthy = False
                    # 即使状态异常，我们也更新时间，这样可以知道异常是什么时候发生的
                    conn.last_heartbeat_time = current_time
                    logger.warning(f"账号 {conn.id} 心跳异常")
                return  # 找到匹配的连接后直接返回
        logger.debug(f"未找到匹配账号 {self_id} 的连接")

    def get_connection_by_id(self, account_id: int) -> Optional[AccountConnection]:
        """根据账号ID获取连接信息"""
        return self.connections.get(account_id)
    
    def get_connection_by_qq(self, bot_qq: str) -> Optional[AccountConnection]:
        """根据QQ号获取连接信息"""
        for conn in self.connections.values():
            if conn.bot_qq == str(bot_qq):
                return conn
        return None
    
    def get_all_connections(self) -> Dict[int, AccountConnection]:
        """获取所有连接"""
        return self.connections.copy()
    
    def is_parallel_mode(self) -> bool:
        """检查是否为并行模式"""
        return self.mode == 'parallel'

    async def _update_group_list_loop(self):
        """Parallel Pro 模式下定时更新群列表"""
        logger.info("启动群列表更新循环")
        
        # 首次运行前等待一段时间，确保所有连接都已建立
        await asyncio.sleep(10)
        
        while self._is_running:
            try:
                await self._fetch_all_group_lists()
                # 每5分钟更新一次
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"群列表更新循环发生异常: {e}", exc_info=True)
                await asyncio.sleep(60)  # 发生异常时1分钟后重试
    
    async def _fetch_all_group_lists(self):
        """获取所有账号的群列表"""
        from utils.api_utils import call_onebot_api
        
        logger.debug("开始获取所有账号的群列表")
        
        success_count = 0
        for account_id, conn in self.connections.items():
            if not conn.is_connected:
                logger.warning(f"账号 {account_id} 未连接，跳过群列表获取")
                continue
            
            if not conn.is_healthy:
                logger.warning(f"账号 {account_id} 不健康，但仍尝试获取群列表")
            
            try:
                result = await call_onebot_api(
                    context=self.context,
                    action='get_group_list',
                    params={},
                    account_id=account_id
                )
                
                if result and result.get('success'):
                    data = result.get('data', {})
                    if data.get('status') == 'ok' and 'data' in data:
                        group_list = data['data']
                        self._group_list_cache[account_id] = group_list
                        logger.debug(f"账号 {account_id} 获取到 {len(group_list)} 个群")
                        success_count += 1
                    else:
                        logger.warning(f"账号 {account_id} 获取群列表失败：{data}")
                else:
                    logger.warning(f"账号 {account_id} 获取群列表失败：{result}")
                    
            except Exception as e:
                logger.error(f"获取账号 {account_id} 群列表时发生异常：{e}")
        
        # 更新群 - 账号映射
        self._update_group_accounts_map()
        
        # 统计总连接数和成功获取群列表的账号数
        total_connected = sum(1 for conn in self.connections.values() if conn.is_connected)
        logger.info(f"群列表更新完成，缓存了 {success_count}/{total_connected} 个已连接账号的群列表")
        
        # 如果有账号未成功获取群列表，记录警告
        if success_count < total_connected:
            logger.warning(f"有 {total_connected - success_count} 个已连接账号未能获取群列表，优先级判断可能不准确")
    
    def _update_group_accounts_map(self):
        """更新群-账号映射关系"""
        self._group_accounts_map.clear()
        
        for account_id, group_list in self._group_list_cache.items():
            for group in group_list:
                group_id = str(group.get('group_id'))
                if group_id not in self._group_accounts_map:
                    self._group_accounts_map[group_id] = []
                self._group_accounts_map[group_id].append(account_id)
        
        # 统计有多个账号的群
        multi_account_groups = [
            (gid, accounts) for gid, accounts in self._group_accounts_map.items()
            if len(accounts) > 1
        ]
        
        if multi_account_groups:
            logger.info(f"发现 {len(multi_account_groups)} 个群有多个账号共存")
            for gid, accounts in multi_account_groups[:5]:  # 只显示前5个
                logger.debug(f"群 {gid}: 账号 {accounts}")
    
    def get_accounts_in_group(self, group_id: str) -> List[int]:
        """获取指定群中的所有账号ID列表"""
        return self._group_accounts_map.get(str(group_id), [])
    
    def is_highest_priority_in_group(self, account_id: int, group_id: str) -> bool:
        """检查指定账号是否是该群中优先级最高的活跃账号
        
        Args:
            account_id: 要检查的账号 ID
            group_id: 群 ID
            
        Returns:
            True 如果该账号是该群最高优先级的活跃账号，否则 False
        """
        accounts_in_group = self.get_accounts_in_group(group_id)
        
        # 如果该群只有一个账号或没有缓存信息，直接返回 True
        if len(accounts_in_group) <= 1:
            logger.debug(f"群 {group_id} 只有 {len(accounts_in_group)} 个账号缓存，允许处理")
            return True
        
        # 获取当前账号的优先级
        current_conn = self.connections.get(account_id)
        if not current_conn:
            logger.warning(f"账号 {account_id} 的连接信息不存在")
            return False
        
        # 如果当前账号未连接或不健康，不应该处理消息
        if not current_conn.is_connected or not current_conn.is_healthy:
            logger.debug(f"账号 {account_id} 未连接或不健康，不应该处理消息")
            return False
        
        current_priority = current_conn.priority
        
        # 检查是否有其他更高优先级的活跃账号
        for other_account_id in accounts_in_group:
            if other_account_id == account_id:
                continue
            
            other_conn = self.connections.get(other_account_id)
            if not other_conn:
                continue
            
            # 如果其他账号优先级更高且活跃，返回 False
            if other_conn.priority < current_priority and other_conn.is_connected and other_conn.is_healthy:
                logger.debug(f"账号 {account_id} 在群 {group_id} 中有更高优先级的账号 {other_account_id} (优先级：{other_conn.priority} < {current_priority})")
                return False
        
        logger.debug(f"账号 {account_id} 是群 {group_id} 中最高优先级的活跃账号 (优先级：{current_priority})")
        return True
    
    def is_parallel_pro_mode(self) -> bool:
        """检查是否为 Parallel Pro 模式"""
        return self.mode == 'parallel-pro'

    def stop(self):
        """停止主循环。"""
        logger.debug("MultiWebSocketManager停止主循环")
        self._is_running = False