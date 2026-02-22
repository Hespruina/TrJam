# plugin_system/plugin_manager.py
# 插件管理器，负责插件的生命周期管理

import os
import sys
import importlib
import importlib.util
import asyncio
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path
from plugin_system.plugin_base import PluginBase, PluginContext, PluginInfo
from plugin_system.event_bus import EventBus
from plugin_system.service_registry import ServiceRegistry
from plugin_system.logger_factory import LoggerFactory
from plugin_system.exceptions import PluginLoadError, PluginDependencyError
from logger_config import get_logger


logger = get_logger("PluginManager")


class PluginManager:
    """插件管理器，负责插件的生命周期管理"""
    
    def __init__(self, core_context, plugins_dir: str = "plugins"):
        self.core_context = core_context
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, PluginInfo] = {}  # plugin_id -> PluginInfo
        self.event_bus = EventBus()
        self.service_registry = ServiceRegistry()
        self.logger = get_logger("PluginManager")
        self._lock = asyncio.Lock()
    
    async def load_all(self) -> Dict[str, bool]:
        """加载所有插件
        
        Returns:
            加载结果字典 {plugin_name: success}
        """
        self.logger.info("开始加载所有插件...")
        results = {}
        
        if not os.path.exists(self.plugins_dir):
            self.logger.warning(f"插件目录不存在: {self.plugins_dir}")
            try:
                os.makedirs(self.plugins_dir, exist_ok=True)
                self.logger.info(f"创建插件目录: {self.plugins_dir}")
            except Exception as e:
                self.logger.error(f"创建插件目录失败: {e}")
            return results
        
        for plugin_name in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, plugin_name)
            if os.path.isdir(plugin_path):
                success = await self.load(plugin_name)
                results[plugin_name] = success
        
        success_count = sum(1 for s in results.values() if s)
        self.logger.info(f"插件加载完成: 成功 {success_count}/{len(results)}")
        return results
    
    async def load(self, plugin_name: str) -> bool:
        """加载单个插件
        
        Args:
            plugin_name: 插件名称（即插件目录名）
            
        Returns:
            是否加载成功
        """
        plugin_path = os.path.join(self.plugins_dir, plugin_name)
        plugin_id = plugin_name
        
        try:
            async with self._lock:
                # 1. 检查是否已加载
                if plugin_id in self.plugins:
                    self.logger.warning(f"插件 {plugin_id} 已加载")
                    return False
                
                # 2. 读取插件元信息
                meta = await self._load_plugin_meta(plugin_path)
                if not meta:
                    return False
                
                self.logger.info(f"正在加载插件: {plugin_id} v{meta.get('version', 'N/A')}")
                
                # 3. 检查依赖
                if not await self._check_dependencies(meta):
                    return False
                
                # 4. 创建插件上下文
                config = meta.get('config', {})
                context = PluginContext(
                    plugin_id=plugin_id,
                    config=config,
                    logger=LoggerFactory.get_logger(plugin_id),
                    core_context=self.core_context,
                    service_registry=self.service_registry,
                    event_bus=self.event_bus
                )
                
                # 5. 动态导入插件模块
                entry_point = meta.get('entry_point', 'main:Plugin')
                if ':' not in entry_point:
                    entry_point = f'main:{entry_point}'
                
                module_name, class_name = entry_point.split(':')
                
                # 将插件目录添加到 sys.path
                plugin_sys_path = os.path.abspath(self.plugins_dir)
                if plugin_sys_path not in sys.path:
                    sys.path.insert(0, plugin_sys_path)
                
                # 加载模块
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{plugin_name}.{module_name}",
                    os.path.join(plugin_path, f"{module_name}.py")
                )
                
                if spec is None or spec.loader is None:
                    self.logger.error(f"无法加载插件模块: {module_name}")
                    return False
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"plugins.{plugin_name}.{module_name}"] = module
                spec.loader.exec_module(module)
                
                # 6. 实例化插件
                plugin_class = getattr(module, class_name)
                plugin_instance = plugin_class(plugin_id, context)
                
                # 7. 调用生命周期钩子
                await plugin_instance.on_load()
                
                # 8. 注册事件订阅（从元信息）
                await self._register_event_handlers(meta, plugin_instance)
                
                # 9. 注册命令（从元信息）
                await self._register_commands(meta, plugin_instance)
                
                # 10. 根据配置决定是否启用
                should_enable = config.get('enabled', True)
                if should_enable:
                    await plugin_instance.on_enable()
                    status = 'enabled'
                else:
                    status = 'disabled'
                
                # 11. 存储插件信息
                self.plugins[plugin_id] = PluginInfo(
                    id=plugin_id,
                    meta=meta,
                    instance=plugin_instance,
                    context=context,
                    status=status
                )
                
                self.logger.info(f"插件 {plugin_id} 加载成功 (状态: {status})")
                return True
                
        except Exception as e:
            self.logger.error(f"加载插件 {plugin_id} 失败: {e}", exc_info=True)
            return False
    
    async def unload(self, plugin_id: str) -> bool:
        """卸载插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否卸载成功
        """
        async with self._lock:
            if plugin_id not in self.plugins:
                self.logger.warning(f"插件 {plugin_id} 未加载")
                return False
            
            try:
                plugin_info = self.plugins[plugin_id]
                
                # 调用禁用钩子
                if plugin_info.status == 'enabled':
                    await plugin_info.instance.on_disable()
                
                # 调用卸载钩子
                await plugin_info.instance.on_unload()
                
                # 清理事件订阅
                await self.event_bus.clear_plugin(plugin_id)
                
                # 清理服务注册
                await self.service_registry.clear_plugin(plugin_id)
                
                # 清理插件命令从全局命令列表
                if hasattr(self.core_context, 'config') and isinstance(self.core_context.config, dict):
                    commands = self.core_context.config.get('commands', {})
                    commands_to_remove = []
                    for cmd_name, cmd_config in commands.items():
                        if cmd_config.get('plugin_id') == plugin_id:
                            commands_to_remove.append(cmd_name)
                    for cmd_name in commands_to_remove:
                        del self.core_context.config['commands'][cmd_name]
                        self.logger.debug(f"从全局命令列表移除插件 {plugin_id} 的命令: {cmd_name}")
                
                # 移除插件
                del self.plugins[plugin_id]
                
                self.logger.info(f"插件 {plugin_id} 卸载成功")
                return True
            except Exception as e:
                self.logger.error(f"卸载插件 {plugin_id} 失败: {e}", exc_info=True)
                return False
    
    async def reload(self, plugin_id: str) -> bool:
        """重载插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否重载成功
        """
        self.logger.info(f"正在重载插件: {plugin_id}")
        if await self.unload(plugin_id):
            return await self.load(plugin_id)
        return False
    
    async def enable(self, plugin_id: str) -> bool:
        """启用插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否启用成功
        """
        if plugin_id not in self.plugins:
            self.logger.warning(f"插件 {plugin_id} 未加载")
            return False
        
        plugin_info = self.plugins[plugin_id]
        if plugin_info.status == 'enabled':
            return True
        
        try:
            await plugin_info.instance.on_enable()
            plugin_info.status = 'enabled'
            self.logger.info(f"插件 {plugin_id} 已启用")
            return True
        except Exception as e:
            self.logger.error(f"启用插件 {plugin_id} 失败: {e}", exc_info=True)
            return False
    
    async def disable(self, plugin_id: str) -> bool:
        """禁用插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            是否禁用成功
        """
        if plugin_id not in self.plugins:
            self.logger.warning(f"插件 {plugin_id} 未加载")
            return False
        
        plugin_info = self.plugins[plugin_id]
        if plugin_info.status == 'disabled':
            return True
        
        try:
            await plugin_info.instance.on_disable()
            plugin_info.status = 'disabled'
            self.logger.info(f"插件 {plugin_id} 已禁用")
            return True
        except Exception as e:
            self.logger.error(f"禁用插件 {plugin_id} 失败: {e}", exc_info=True)
            return False
    
    async def dispatch_event(self, event_type: str, event_data: dict) -> dict:
        """分发事件到插件
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
            
        Returns:
            处理结果
        """
        return await self.event_bus.emit(event_type, event_data)
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            插件信息
        """
        return self.plugins.get(plugin_id)
    
    def list_plugins(self) -> List[PluginInfo]:
        """列出所有插件
        
        Returns:
            插件信息列表
        """
        return list(self.plugins.values())
    
    def get_enabled_plugins(self) -> List[PluginInfo]:
        """获取所有已启用的插件
        
        Returns:
            已启用插件列表
        """
        return [p for p in self.plugins.values() if p.status == 'enabled']
    
    async def handle_account_switch(self, old_account: Optional[Dict[str, Any]], new_account: Dict[str, Any]):
        """处理账号切换事件
        
        Args:
            old_account: 旧账号信息
            new_account: 新账号信息
        """
        self.logger.info(f"处理账号切换事件: 从 {old_account.get('id') if old_account else '无'} 切换到 {new_account.get('id')}")
        
        # 遍历所有已加载的插件，通知账号切换
        for plugin_id, plugin_info in self.plugins.items():
            try:
                if hasattr(plugin_info.instance, 'on_account_switch'):
                    await plugin_info.instance.on_account_switch(old_account, new_account)
                    self.logger.debug(f"通知插件 {plugin_id} 账号切换成功")
            except Exception as e:
                self.logger.error(f"通知插件 {plugin_id} 账号切换失败: {e}")
    
    async def _load_plugin_meta(self, plugin_path: str) -> Optional[dict]:
        """加载插件元信息
        
        Args:
            plugin_path: 插件路径
            
        Returns:
            插件元信息字典
        """
        meta_path = os.path.join(plugin_path, 'plugin.yml')
        if not os.path.exists(meta_path):
            self.logger.error(f"插件元信息文件不存在: {meta_path}")
            return None
        
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"读取插件元信息失败: {e}")
            return None
    
    async def _check_dependencies(self, meta: dict) -> bool:
        """检查插件依赖
        
        Args:
            meta: 插件元信息
            
        Returns:
            是否满足依赖
        """
        dependencies = meta.get('dependencies', {})
        
        # 检查 Python 包依赖
        python_deps = dependencies.get('python', [])
        for dep in python_deps:
            try:
                pkg_name = dep.split('>=')[0].split('==')[0].split('<=')[0].split('~=')[0].strip().lower()
                # 特殊处理一些包名
                pkg_map = {
                    'pillow': 'PIL',
                    'pyyaml': 'yaml',
                    'pytest': None,  # 跳过测试包
                }
                import_name = pkg_map.get(pkg_name, pkg_name)
                if import_name:
                    importlib.import_module(import_name)
            except ImportError:
                self.logger.error(f"缺少依赖: {dep}")
                return False
        
        # 检查插件依赖
        plugin_deps = dependencies.get('plugins', [])
        for dep in plugin_deps:
            dep_name = dep.split('>=')[0].split('==')[0].strip()
            if dep_name not in self.plugins:
                self.logger.error(f"缺少插件依赖: {dep}")
                return False
        
        return True
    
    async def _register_event_handlers(self, meta: dict, plugin_instance: PluginBase):
        """注册事件处理器
        
        Args:
            meta: 插件元信息
            plugin_instance: 插件实例
        """
        events = meta.get('events', {})
        for event_category, handlers in events.items():
            for handler_info in handlers:
                event_name = handler_info.get('event')
                priority = handler_info.get('priority', 100)
                handler_name = handler_info.get('handler')
                
                if hasattr(plugin_instance, handler_name):
                    handler = getattr(plugin_instance, handler_name)
                    await self.event_bus.subscribe(
                        plugin_instance.plugin_id,
                        event_name,
                        handler,
                        priority
                    )
                    self.logger.debug(f"插件 {plugin_instance.plugin_id} 注册事件处理器: {event_name} -> {handler_name}")
                else:
                    self.logger.warning(f"插件 {plugin_instance.plugin_id} 中未找到事件处理器: {handler_name}")
    
    async def _register_commands(self, meta: dict, plugin_instance: PluginBase):
        """注册命令
        
        Args:
            meta: 插件元信息
            plugin_instance: 插件实例
        """
        # 1. 处理插件元信息中的命令配置
        meta_commands = meta.get('commands', [])
        for cmd_info in meta_commands:
            command = cmd_info.get('command')
            handler_name = cmd_info.get('handler')
            
            if command and handler_name and hasattr(plugin_instance, handler_name):
                handler = getattr(plugin_instance, handler_name)
                # 注册事件订阅
                await self.event_bus.subscribe(
                    plugin_instance.plugin_id,
                    f"command:{command}",
                    handler,
                    cmd_info.get('priority', 100)
                )
                self.logger.debug(f"插件 {plugin_instance.plugin_id} 注册命令: {command} -> {handler_name}")
                # 同时通过插件实例注册命令，确保包含完整信息
                plugin_instance.context.register_command(
                    command=command,
                    handler=handler,
                    permission=cmd_info.get('permission', 'User'),
                    description=cmd_info.get('description', ''),
                    usage=cmd_info.get('usage', ''),
                    category=cmd_info.get('category', '通用'),
                    global_available=cmd_info.get('global_available', True)
                )
        
        # 2. 处理插件实例中注册的命令
        instance_commands = plugin_instance.context.list_commands()
        for cmd_name, cmd_info in instance_commands.items():
            # 将插件命令添加到全局命令列表中
            if hasattr(self.core_context, 'config') and isinstance(self.core_context.config, dict):
                if 'commands' not in self.core_context.config:
                    self.core_context.config['commands'] = {}
                # 只添加不存在的命令，避免覆盖主程序命令
                if cmd_name not in self.core_context.config['commands']:
                    # 构建命令配置，匹配commands.yml格式
                    command_config = {
                        'permission': cmd_info.get('permission', 'User'),
                        'description': cmd_info.get('description', ''),
                        'usage': cmd_info.get('usage', ''),
                        'category': cmd_info.get('category', '通用'),
                        'global_available': cmd_info.get('global_available', True),
                        'plugin_id': plugin_instance.plugin_id  # 添加插件ID标识
                    }
                    self.core_context.config['commands'][cmd_name] = command_config
                    self.logger.debug(f"插件 {plugin_instance.plugin_id} 的命令 {cmd_name} 已添加到全局命令列表")
