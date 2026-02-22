# plugin_system/service_registry.py
# 服务注册表，实现跨插件通信

from typing import Dict, Any, Optional
import asyncio


class ServiceRegistry:
    """服务注册表，用于跨插件通信"""
    
    def __init__(self):
        self._services: Dict[str, Dict[str, Any]] = {}  # plugin_id -> {service_name: service}
        self._lock = asyncio.Lock()
    
    async def register(self, plugin_id: str, name: str, service: Any):
        """注册服务
        
        Args:
            plugin_id: 插件ID
            name: 服务名称
            service: 服务对象
        """
        async with self._lock:
            if plugin_id not in self._services:
                self._services[plugin_id] = {}
            self._services[plugin_id][name] = service
    
    def get(self, plugin_id: str, service_name: str) -> Optional[Any]:
        """获取服务
        
        Args:
            plugin_id: 插件ID
            service_name: 服务名称
            
        Returns:
            服务对象，如果不存在则返回None
        """
        if plugin_id in self._services:
            return self._services[plugin_id].get(service_name)
        return None
    
    async def list_services(self, plugin_id: str = None) -> Dict[str, Any]:
        """列出服务
        
        Args:
            plugin_id: 插件ID，如果为None则列出所有服务
            
        Returns:
            服务字典
        """
        async with self._lock:
            if plugin_id:
                return self._services.get(plugin_id, {}).copy()
            return {pid: services.copy() for pid, services in self._services.items()}
    
    async def clear_plugin(self, plugin_id: str):
        """清除插件的所有服务
        
        Args:
            plugin_id: 插件ID
        """
        async with self._lock:
            self._services.pop(plugin_id, None)
    
    async def unregister(self, plugin_id: str, service_name: str) -> bool:
        """取消注册服务
        
        Args:
            plugin_id: 插件ID
            service_name: 服务名称
            
        Returns:
            是否成功取消注册
        """
        async with self._lock:
            if plugin_id in self._services and service_name in self._services[plugin_id]:
                del self._services[plugin_id][service_name]
                return True
            return False
