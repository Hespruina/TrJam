import asyncio
import json
import logging
import os
import random
import string
from typing import Dict, List, Optional
import subprocess
import yaml

from core.port_manager import port_manager
from core.websocket_forwarder import WebSocketForwarder
from logger_config import get_logger

logger = get_logger("SubBotManager")

class SubBotManager:
    """子机器人管理器，负责发现、加载和管理子机器人"""
    
    def __init__(self, parent_ws_url: str, parent_token: str):
        self.parent_ws_url = parent_ws_url
        self.parent_token = parent_token
        self.subbots: Dict[str, Dict] = {}
        self.forwarders: Dict[str, WebSocketForwarder] = {}
        self.running = False
        self.subsystem_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "subbot")
        self.context = None  # 上下文对象，稍后会从外部设置
        self.subbot_metadata: Dict[str, Dict] = {}  # 存储子机器人的元数据
    
    async def start(self):
        """启动子机器人管理器"""
        self.running = True
        logger.info("子机器人管理器已启动")
        
        # 扫描并加载子机器人
        await self.scan_and_load_subbots()
        
        # 自动启动标记为startup的子机器人
        await self._auto_start_startup_subbots()
    
    async def _auto_start_startup_subbots(self):
        """自动启动标记为startup的子机器人"""
        try:
            logger.info("开始检查自动启动的子机器人...")
            logger.info(f"当前已加载的元数据: {list(self.subbot_metadata.keys())}")
            
            startup_subbots = []
            for bot_name, metadata in self.subbot_metadata.items():
                logger.info(f"检查子机器人 {bot_name}: startup={metadata.get('startup', False)}, 兼容性={self._check_compatibility(metadata)}")
                if metadata.get('startup', False) and self._check_compatibility(metadata):
                    startup_subbots.append(bot_name)
            
            if startup_subbots:
                logger.info(f"发现 {len(startup_subbots)} 个需要自动启动的子机器人: {startup_subbots}")
                for bot_name in startup_subbots:
                    logger.info(f"正在自动启动子机器人: {bot_name}")
                    await self.load_subbot(bot_name)
            else:
                logger.info("没有发现需要自动启动的子机器人")
                # 显示所有子机器人的startup状态供调试
                for bot_name, metadata in self.subbot_metadata.items():
                    logger.info(f"子机器人 {bot_name} startup状态: {metadata.get('startup', '未设置')}")
                
        except Exception as e:
            logger.error(f"自动启动子机器人时发生错误: {e}")
    
    async def stop(self):
        """停止子机器人管理器"""
        self.running = False
        logger.info("子机器人管理器正在停止")
        
        # 停止所有子机器人
        for bot_name in list(self.subbots.keys()):
            await self.stop_subbot(bot_name)
        
        # 停止所有转发器
        for forwarder in list(self.forwarders.values()):
            try:
                await forwarder.stop()
            except Exception as e:
                logger.error(f"停止转发器时发生错误: {e}")
        
        self.forwarders.clear()
        self.subbots.clear()
        self.subbot_metadata.clear()
        logger.info("子机器人管理器已停止")
    
    async def scan_and_load_subbots(self):
        """扫描并加载子机器人元数据"""
        if not os.path.exists(self.subsystem_dir):
            logger.warning(f"子机器人目录不存在: {self.subsystem_dir}")
            return
        
        logger.info(f"正在扫描子机器人目录: {self.subsystem_dir}")
        
        # 遍历subbot目录下的所有子目录
        for item in os.listdir(self.subsystem_dir):
            item_path = os.path.join(self.subsystem_dir, item)
            
            # 检查是否是目录且包含__init__.py文件
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
                bot_name = item
                logger.info(f"发现子机器人: {bot_name}")
                
                # 读取元数据
                metadata = self._load_subbot_metadata(bot_name)
                if metadata:
                    self.subbot_metadata[bot_name] = metadata
                    logger.info(f"已加载子机器人 {bot_name} 的元数据")
                else:
                    logger.warning(f"子机器人 {bot_name} 元数据加载失败，将继续处理")
                    # 即使元数据加载失败，也创建一个基本的元数据条目
                    self.subbot_metadata[bot_name] = {
                        'name': bot_name,
                        'version': 'N/A',
                        'description': '元数据加载失败',
                        'author': '未知',
                        'startup': False  # 默认不自动启动
                    }
    
    def _load_subbot_metadata(self, bot_name: str) -> Optional[Dict]:
        """加载子机器人的元数据"""
        try:
            metadata_path = os.path.join(self.subsystem_dir, bot_name, "subbot.yml")
            
            logger.info(f"尝试加载子机器人 {bot_name} 的元数据文件: {metadata_path}")
            logger.info(f"文件是否存在: {os.path.exists(metadata_path)}")
            
            if not os.path.exists(metadata_path):
                logger.warning(f"子机器人 {bot_name} 缺少 subbot.yml 文件: {metadata_path}")
                # 列出该目录下的所有文件供调试
                bot_dir = os.path.join(self.subsystem_dir, bot_name)
                if os.path.exists(bot_dir):
                    files = os.listdir(bot_dir)
                    logger.info(f"目录 {bot_dir} 中的文件: {files}")
                return None
            
            # 尝试读取文件内容
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logger.debug(f"文件内容预览: {content[:200]}...")
            except Exception as read_error:
                logger.error(f"读取文件 {metadata_path} 失败: {read_error}")
                return None
            
            # 解析YAML
            try:
                metadata = yaml.safe_load(content)
                logger.debug(f"成功解析YAML，原始数据: {metadata}")
            except Exception as yaml_error:
                logger.error(f"解析YAML失败: {yaml_error}")
                return None
            
            # 验证必需字段
            required_fields = ['name', 'version', 'description']
            missing_fields = [field for field in required_fields if field not in metadata]
            if missing_fields:
                logger.error(f"子机器人 {bot_name} 的元数据缺少必需字段: {missing_fields}")
                logger.error(f"当前元数据字段: {list(metadata.keys())}")
                return None
            
            # 验证name字段是否匹配目录名
            if metadata['name'] != bot_name:
                logger.warning(f"子机器人 {bot_name} 的元数据name字段({metadata['name']})与目录名不匹配")
            
            logger.debug(f"子机器人 {bot_name} 元数据验证通过: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"加载子机器人 {bot_name} 元数据时发生未预期的错误: {e}", exc_info=True)
            return None
    
    async def load_subbot(self, bot_name: str):
        """加载子机器人"""
        try:
            # 检查元数据是否存在
            if bot_name not in self.subbot_metadata:
                logger.warning(f"子机器人 {bot_name} 没有有效的元数据，跳过加载")
                return
            
            # 检查兼容性
            metadata = self.subbot_metadata[bot_name]
            if not self._check_compatibility(metadata):
                logger.warning(f"子机器人 {bot_name} 与当前版本不兼容，跳过加载")
                return
            
            # 生成唯一的token
            token = self._generate_token()
            
            # 分配可用端口
            port = port_manager.get_available_port()
            if not port:
                logger.error(f"无法为子机器人 {bot_name} 分配端口")
                return
            
            # 创建WebSocket转发器
            forwarder = WebSocketForwarder(port, token)
            
            # 设置消息处理回调函数，将子机器人的消息转发给主机器人
            async def handle_subbot_message(message: str):
                """处理子机器人发送的消息"""
                try:
                    # 这里需要将消息传递给主机器人的消息处理系统
                    # 由于我们没有直接的访问权限，我们可以通过上下文获取消息路由器
                    if hasattr(self, 'context') and hasattr(self.context, 'message_router'):
                        logger.info(f"转发子机器人消息到主机器人: {message}")
                        
                        # 解析子机器人发送的消息
                        data = json.loads(message)
                        
                        # 检查是否是发送消息的请求
                        if data.get('action') in ['send_private_msg', 'send_group_msg', 'send_msg', 'send_group_forward_msg']:
                            # 尝试通过上下文获取多WebSocket管理器
                            if hasattr(self.context, 'multi_ws_manager'):
                                multi_ws_manager = self.context.multi_ws_manager
                                
                                # 获取当前活跃的连接
                                if hasattr(multi_ws_manager, 'connections') and hasattr(multi_ws_manager, 'active_connection_id'):
                                    active_conn_id = multi_ws_manager.active_connection_id
                                    if active_conn_id in multi_ws_manager.connections:
                                        active_conn = multi_ws_manager.connections[active_conn_id]
                                        
                                        # 检查连接是否可用
                                        if active_conn.is_connected and active_conn.websocket:
                                            # 直接通过WebSocket连接发送消息
                                            # 注意：在aiohttp中，ClientWebSocketResponse发送消息的方法是send_str
                                            await active_conn.websocket.send_str(message)
                                            logger.info(f"已通过活跃连接 {active_conn_id} 发送子机器人消息")
                                        else:
                                            logger.error(f"活跃连接 {active_conn_id} 不可用")
                                    else:
                                        logger.error(f"活跃连接 {active_conn_id} 不存在")
                                else:
                                    logger.error("无法获取多WebSocket管理器的连接信息")
                            else:
                                logger.error("上下文中没有多WebSocket管理器")
                except Exception as e:
                    logger.error(f"处理子机器人消息时发生错误: {e}")
            
            forwarder.set_message_handler(handle_subbot_message)
            await forwarder.start()
            
            # 不再需要连接主机器人，主机器人会直接将消息转发给转发器
            # 只需要启动转发器即可
            logger.info(f"子机器人 {bot_name} 转发器已启动，等待子机器人连接")
            
            # 生成启动命令
            start_command = self._generate_start_command(bot_name, port, token)
            
            # 启动子机器人进程
            process = await self._start_subbot_process(bot_name, start_command)
            
            # 存储子机器人信息
            self.subbots[bot_name] = {
                "port": port,
                "token": token,
                "process": process,
                "status": "running",
                "last_start_time": asyncio.get_event_loop().time(),
                "metadata": metadata  # 添加元数据引用
            }
            
            # 存储转发器
            self.forwarders[bot_name] = forwarder
            
            logger.info(f"子机器人 {bot_name} 已成功加载，端口: {port}")
            
            # 启动监控任务
            asyncio.create_task(self._monitor_subbot(bot_name))
            
        except Exception as e:
            logger.error(f"加载子机器人 {bot_name} 失败: {e}")
    
    def _check_compatibility(self, metadata: Dict) -> bool:
        """检查子机器人与当前版本的兼容性"""
        try:
            # 获取当前主机器人版本（假设从某个地方获取）
            current_version = "3.5.0"  # 这里应该从实际配置中获取
            
            compatible_versions = metadata.get('metadata', {}).get('compatible_versions', [])
            
            if not compatible_versions:
                logger.warning(f"子机器人 {metadata['name']} 没有指定兼容版本信息")
                return True  # 默认认为兼容
            
            # 简单的版本比较（实际应用中可能需要更复杂的版本比较逻辑）
            for version_range in compatible_versions:
                if version_range.startswith('>='):
                    min_version = version_range[2:]
                    if self._compare_versions(current_version, min_version) >= 0:
                        return True
                elif version_range.startswith('>'):
                    min_version = version_range[1:]
                    if self._compare_versions(current_version, min_version) > 0:
                        return True
                elif version_range.startswith('<='):
                    max_version = version_range[2:]
                    if self._compare_versions(current_version, max_version) <= 0:
                        return True
                elif version_range.startswith('<'):
                    max_version = version_range[1:]
                    if self._compare_versions(current_version, max_version) < 0:
                        return True
                elif version_range == current_version:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查兼容性时发生错误: {e}")
            return False
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较两个版本号"""
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            
            # 补齐版本号位数
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            # 逐位比较
            for i in range(max_len):
                if v1_parts[i] > v2_parts[i]:
                    return 1
                elif v1_parts[i] < v2_parts[i]:
                    return -1
            
            return 0
        except Exception:
            return 0  # 比较失败时返回相等
    
    async def stop_subbot(self, bot_name: str):
        """停止子机器人"""
        if bot_name not in self.subbots:
            logger.warning(f"子机器人 {bot_name} 不存在")
            return
        
        try:
            # 获取子机器人信息
            bot_info = self.subbots[bot_name]
            
            # 停止转发器（先停止转发器，避免消息继续传递）
            if bot_name in self.forwarders:
                try:
                    await self.forwarders[bot_name].stop()
                    del self.forwarders[bot_name]
                    logger.debug(f"已停止子机器人 {bot_name} 的转发器")
                except Exception as e:
                    logger.error(f"停止子机器人 {bot_name} 转发器时发生错误: {str(e)}")
            
            # 终止进程（使用非阻塞方式）
            if bot_info.get("process"):
                try:
                    process = bot_info["process"]
                    process.terminate()
                    
                    # 使用非阻塞方式等待进程退出
                    async def wait_for_process_exit(process, timeout):
                        """非阻塞等待进程退出"""
                        start_time = asyncio.get_event_loop().time()
                        while asyncio.get_event_loop().time() - start_time < timeout:
                            # 对于asyncio.subprocess.Process，使用returncode属性
                            if process.returncode is not None:
                                return process.returncode
                            await asyncio.sleep(0.1)
                        return None
                    
                    exit_code = await wait_for_process_exit(process, timeout=2.0)
                    if exit_code is None:
                        logger.warning(f"子机器人 {bot_name} 进程在2秒内未退出，强制杀死")
                        process.kill()
                        # 再次尝试等待，但不阻塞主线程
                        asyncio.create_task(wait_for_process_exit(process, timeout=1.0))
                    else:
                        logger.debug(f"子机器人 {bot_name} 进程已退出，退出码: {exit_code}")
                except Exception as e:
                    logger.error(f"停止子机器人 {bot_name} 进程时发生错误: {str(e)}")
            
            # 释放端口
            port = bot_info.get("port")
            if port:
                port_manager.release_port(port)
                logger.debug(f"已释放子机器人 {bot_name} 的端口: {port}")
            
            # 移除子机器人信息
            del self.subbots[bot_name]
            
            logger.info(f"子机器人 {bot_name} 已成功停止")
            
        except Exception as e:
            logger.error(f"停止子机器人 {bot_name} 时发生错误: {str(e)}")
    
    async def _start_subbot_process(self, bot_name: str, start_command: str) -> Optional[object]:
        """启动子机器人进程"""
        try:
            bot_dir = os.path.join(self.subsystem_dir, bot_name)
            
            # 启动进程
            process = await asyncio.create_subprocess_shell(
                start_command,
                cwd=bot_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 启动输出捕获任务
            asyncio.create_task(self._capture_subbot_output(bot_name, process))
            
            return process
        except Exception as e:
            logger.error(f"启动子机器人 {bot_name} 进程失败: {e}")
            return None
    
    async def _capture_subbot_output(self, bot_name: str, process: object):
        """捕获子机器人进程的输出"""
        async def read_stream(stream, prefix):
            while True:
                line = await stream.readline()
                if not line:
                    break
                try:
                    line_str = line.decode('utf-8').strip()
                    logger.info(f"[{bot_name} {prefix}] {line_str}")
                except:
                    pass
        
        if process.stdout:
            asyncio.create_task(read_stream(process.stdout, "STDOUT"))
        
        if process.stderr:
            asyncio.create_task(read_stream(process.stderr, "STDERR"))
    
    async def _monitor_subbot(self, bot_name: str):
        """监控子机器人状态"""
        while self.running and bot_name in self.subbots:
            try:
                process = self.subbots[bot_name].get("process")
                if process:
                    # 检查进程是否仍在运行
                    try:
                        # 对于asyncio.subprocess.Process，使用returncode属性
                        if process.returncode is not None:
                            logger.error(f"子机器人 {bot_name} 进程已退出，退出码: {process.returncode}")
                            
                            # 尝试重启子机器人
                            await self._restart_subbot(bot_name)
                    except AttributeError as e:
                        # 如果发生其他属性错误，记录错误信息
                        logger.debug(f"检查进程状态时发生错误: {str(e)}")
                
                await asyncio.sleep(10)  # 每10秒检查一次
            except Exception as e:
                logger.error(f"监控子机器人 {bot_name} 时发生错误: {e}")
                await asyncio.sleep(10)
    
    async def _restart_subbot(self, bot_name: str):
        """重启子机器人"""
        logger.info(f"尝试重启子机器人 {bot_name}")
        
        # 停止子机器人
        await self.stop_subbot(bot_name)
        
        # 重新加载子机器人
        await self.load_subbot(bot_name)
    
    def _generate_token(self) -> str:
        """生成唯一的安全token"""
        import secrets
        return secrets.token_urlsafe(32)
    
    def _generate_start_command(self, bot_name: str, port: int, token: str) -> str:
        """生成子机器人启动命令"""
        # 获取Python解释器路径
        import sys
        python_exe = sys.executable
        
        # 获取入口点配置
        entry_point = self.subbot_metadata.get(bot_name, {}).get('entry_point', '__init__.py')
        
        # 生成启动命令，运行指定的入口文件
        init_file = os.path.join(self.subsystem_dir, bot_name, entry_point)
        return f"{python_exe} {init_file} --ws_port {port} --token {token}"
    
    def get_subbots(self) -> Dict[str, Dict]:
        """获取所有子机器人信息"""
        return self.subbots.copy()
    
    def get_subbot_status(self, bot_name: str) -> Optional[str]:
        """获取子机器人状态"""
        if bot_name in self.subbots:
            return self.subbots[bot_name].get("status")
        return None
    
    def get_subbot_metadata(self, bot_name: str) -> Optional[Dict]:
        """获取子机器人的元数据"""
        return self.subbot_metadata.get(bot_name)
    
    def get_all_subbot_metadata(self) -> Dict[str, Dict]:
        """获取所有子机器人的元数据"""
        return self.subbot_metadata.copy()
    
    def get_compatible_subbots(self) -> List[str]:
        """获取所有兼容的子机器人列表"""
        compatible_bots = []
        for bot_name, metadata in self.subbot_metadata.items():
            if self._check_compatibility(metadata):
                compatible_bots.append(bot_name)
        return compatible_bots