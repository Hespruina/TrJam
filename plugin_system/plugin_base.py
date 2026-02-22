# plugin_system/plugin_base.py
# 插件基类和相关数据结构

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
import asyncio
from plugin_system.logger_factory import LoggerFactory
from plugin_system.exceptions import PluginError
from utils.message_sender.message_builder import MessageBuilder


@dataclass
class PluginInfo:
    """插件信息数据类"""
    id: str  # 插件ID
    meta: Dict[str, Any]  # 插件元信息
    instance: 'PluginBase'  # 插件实例
    context: 'PluginContext'  # 插件上下文
    status: str  # 状态: enabled, disabled, error
    load_time: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class PluginContext:
    """插件上下文，提供受控的资源访问接口"""
    
    def __init__(
        self,
        plugin_id: str,
        config: dict,
        logger,
        core_context,
        service_registry,
        event_bus
    ):
        self.plugin_id = plugin_id
        self.config = config
        self.logger = logger
        self.core_context = core_context
        self.service_registry = service_registry
        self.event_bus = event_bus
        self._command_handlers = {}
    
    async def send_group_message(self, group_id: str, message: list) -> Optional[str]:
        """发送群消息（受控接口）
        
        Args:
            group_id: 群ID
            message: 消息列表（CQ码格式）
            
        Returns:
            消息ID
        """
        try:
            return await self.core_context.send_group_message(group_id, message)
        except Exception as e:
            self.logger.error(f"发送群消息失败: {e}")
            return None
    
    async def send_private_message(self, user_id: str, message: list) -> Optional[str]:
        """发送私聊消息（受控接口）
        
        Args:
            user_id: 用户ID
            message: 消息列表（CQ码格式）
            
        Returns:
            消息ID
        """
        try:
            return await self.core_context.send_private_message(user_id, message)
        except Exception as e:
            self.logger.error(f"发送私聊消息失败: {e}")
            return None
    
    async def call_api(self, action: str, params: dict) -> dict:
        """调用 OneBot API（受控接口）
        
        Args:
            action: API动作
            params: 参数字典
            
        Returns:
            API响应
        """
        try:
            if hasattr(self.core_context, 'message_router'):
                return await self.core_context.message_router.call_api(action, params)
            else:
                self.logger.error("消息路由器不可用")
                return {"status": "failed", "retcode": -1, "data": None}
        except Exception as e:
            self.logger.error(f"调用 API 失败: {e}")
            return {"status": "failed", "retcode": -2, "data": None}
    
    async def register_service(self, name: str, service: Any):
        """注册服务
        
        Args:
            name: 服务名称
            service: 服务对象或函数
        """
        await self.service_registry.register(self.plugin_id, name, service)
        self.logger.info(f"注册服务: {name}")
    
    def get_service(self, plugin_id: str, service_name: str):
        """获取服务（跨插件通信）
        
        Args:
            plugin_id: 插件ID
            service_name: 服务名称
            
        Returns:
            服务对象
        """
        return self.service_registry.get(plugin_id, service_name)
    
    def register_command(self, command: str, handler: Callable, permission: str = "User", description: str = "", usage: str = "", category: str = "通用", global_available: bool = True, **kwargs):
        """注册命令
        
        Args:
            command: 命令名称
            handler: 处理函数
            permission: 权限级别 (User, Admin, Root)
            description: 命令描述
            usage: 命令用法
            category: 命令分类
            global_available: 是否全局可用
            **kwargs: 其他参数（aliases等）
        """
        self._command_handlers[command] = {
            'handler': handler,
            'permission': permission,
            'description': description,
            'usage': usage,
            'category': category,
            'global_available': global_available,
            **kwargs
        }
        self.logger.info(f"注册命令: {command} (权限: {permission}, 分类: {category})")
    
    def get_command_handler(self, command: str) -> Optional[dict]:
        """获取命令处理器
        
        Args:
            command: 命令名称
            
        Returns:
            命令处理器信息
        """
        return self._command_handlers.get(command)
    
    def list_commands(self) -> Dict[str, dict]:
        """列出所有命令
        
        Returns:
            命令字典
        """
        return self._command_handlers.copy()
    
    async def subscribe_event(self, event_type: str, handler: Callable, priority: int = 100):
        """订阅事件
        
        Args:
            event_type: 事件类型
            handler: 处理函数
            priority: 优先级（数字越大优先级越高）
        """
        await self.event_bus.subscribe(self.plugin_id, event_type, handler, priority)
    
    def emit_event(self, event_type: str, data: dict):
        """触发事件（跨插件通信）
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        asyncio.create_task(self.event_bus.emit(event_type, data))
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        # 先从插件自己的配置中获取
        value = self.config.get(key, default)
        if value is not default:
            return value
        
        # 如果插件配置中没有，尝试从核心上下文中获取
        if hasattr(self.core_context, 'get_config_value'):
            return self.core_context.get_config_value(key, default)
        
        return default
    
    def update_config(self, new_config: dict):
        """更新配置
        
        Args:
            new_config: 新配置字典
        """
        self.config.update(new_config)
    
    def builder(self) -> MessageBuilder:
        """创建消息构建器
        
        Returns:
            MessageBuilder实例
        """
        return MessageBuilder(self.core_context)
    
    def group_builder(self, group_id: str, user_id: str = None) -> MessageBuilder:
        """创建群消息构建器
        
        Args:
            group_id: 群ID
            user_id: 用户ID（可选，用于@功能）
            
        Returns:
            配置好的MessageBuilder实例
        """
        builder = MessageBuilder(self.core_context)
        builder.set_group_id(group_id)
        if user_id:
            builder.set_user_id(user_id)
        return builder
    
    def private_builder(self, user_id: str) -> MessageBuilder:
        """创建私聊消息构建器
        
        Args:
            user_id: 用户ID
            
        Returns:
            配置好的MessageBuilder实例
        """
        builder = MessageBuilder(self.core_context)
        builder.set_user_id(user_id)
        return builder
    
    def get_active_account(self) -> Optional[Dict[str, Any]]:
        """获取当前活跃账号信息
        
        Returns:
            当前活跃账号信息
        """
        return self.core_context.get_active_account()
    
    def should_handle_message(self, event: dict) -> bool:
        """检查是否应该处理该消息（基于当前活跃账号）
        
        Args:
            event: 消息事件
            
        Returns:
            是否应该处理该消息
        """
        return self.core_context.should_handle_message(event)


class PluginBase(ABC):
    """插件基类，所有插件必须继承此类"""
    
    def __init__(self, plugin_id: str, context: PluginContext):
        self.plugin_id = plugin_id
        self.context = context
        self.logger = context.logger
        self.config = context.config
        self._enabled = True
        self._tasks = []
    
    @property
    def enabled(self) -> bool:
        """插件是否启用"""
        return self._enabled
    
    @abstractmethod
    async def on_load(self) -> None:
        """插件加载时调用"""
        pass
    
    async def on_enable(self) -> None:
        """插件启用时调用"""
        self._enabled = True
    
    async def on_disable(self) -> None:
        """插件禁用时调用"""
        self._enabled = False
    
    async def on_unload(self) -> None:
        """插件卸载时调用"""
        await self._cleanup()
    
    async def on_config_change(self, old_config: dict, new_config: dict) -> None:
        """配置变化时调用
        
        Args:
            old_config: 旧配置
            new_config: 新配置
        """
        pass
    
    async def on_account_switch(self, old_account: Optional[Dict[str, Any]], new_account: Dict[str, Any]) -> None:
        """账号切换时调用
        
        Args:
            old_account: 旧账号信息
            new_account: 新账号信息
        """
        pass
    
    def create_background_task(self, coro, name: str = None):
        """创建后台任务
        
        Args:
            coro: 协程
            name: 任务名称
            
        Returns:
            任务对象
        """
        task = asyncio.create_task(coro, name=name or f"{self.plugin_id}_bg_task")
        self._tasks.append(task)
        return task
    
    async def _cleanup(self) -> None:
        """清理资源"""
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error(f"清理后台任务时发生错误: {e}")
        self._tasks.clear()
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.plugin_id} enabled={self._enabled}>"
