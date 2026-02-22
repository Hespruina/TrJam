# plugin_system/event_bus.py
# 事件总线，管理事件订阅和分发

from typing import Dict, List, Tuple, Callable, Any
import asyncio
from logger_config import get_logger


logger = get_logger("EventBus")


class EventBus:
    """事件总线，管理事件订阅和分发"""
    
    def __init__(self):
        # {event_type: [(priority, plugin_id, handler), ...]}
        self._subscribers: Dict[str, List[Tuple[int, str, Callable]]] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, plugin_id: str, event_type: str, handler: Callable, priority: int = 100):
        """订阅事件
        
        Args:
            plugin_id: 插件ID
            event_type: 事件类型
            handler: 事件处理函数
            priority: 优先级，数字越大优先级越高
        """
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append((priority, plugin_id, handler))
            # 按优先级排序（降序）
            self._subscribers[event_type].sort(key=lambda x: -x[0])
            logger.debug(f"插件 {plugin_id} 订阅事件 {event_type} (优先级: {priority})")
    
    async def unsubscribe(self, plugin_id: str, event_type: str = None):
        """取消订阅
        
        Args:
            plugin_id: 插件ID
            event_type: 事件类型，如果为None则取消所有订阅
        """
        async with self._lock:
            if event_type:
                if event_type in self._subscribers:
                    original_count = len(self._subscribers[event_type])
                    self._subscribers[event_type] = [
                        (p, pid, h) for p, pid, h in self._subscribers[event_type]
                        if pid != plugin_id
                    ]
                    if len(self._subscribers[event_type]) < original_count:
                        logger.debug(f"插件 {plugin_id} 取消订阅事件 {event_type}")
            else:
                for et in list(self._subscribers.keys()):
                    original_count = len(self._subscribers[et])
                    self._subscribers[et] = [
                        (p, pid, h) for p, pid, h in self._subscribers[et]
                        if pid != plugin_id
                    ]
                    if len(self._subscribers[et]) < original_count:
                        logger.debug(f"插件 {plugin_id} 取消订阅事件 {et}")
    
    async def emit(self, event_type: str, data: dict) -> Dict[str, Any]:
        """分发事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
            
        Returns:
            处理结果字典
                - processed: 是否有插件处理了该事件
                - blocked: 事件是否被阻断
                - results: 各插件的处理结果
        """
        if event_type not in self._subscribers:
            return {"processed": False, "blocked": False, "results": {}}
        
        results = {}
        blocked = False
        subscribers = self._subscribers[event_type].copy()
        
        logger.debug(f"分发事件 {event_type}，共有 {len(subscribers)} 个订阅者")
        
        # 按优先级顺序执行
        for priority, plugin_id, handler in subscribers:
            try:
                result = await handler(data)
                results[plugin_id] = result
                
                # 检查是否需要阻断事件
                if isinstance(result, dict) and result.get('block_event', False):
                    blocked = True
                    logger.debug(f"事件 {event_type} 被 {plugin_id} 阻断")
                    break
                    
            except Exception as e:
                logger.error(f"插件 {plugin_id} 处理事件 {event_type} 时发生错误: {e}", exc_info=True)
                results[plugin_id] = {"error": str(e)}
        
        return {"processed": True, "blocked": blocked, "results": results}
    
    async def clear_plugin(self, plugin_id: str):
        """清除插件的所有订阅
        
        Args:
            plugin_id: 插件ID
        """
        await self.unsubscribe(plugin_id)
    
    async def get_subscribers(self, event_type: str = None) -> Dict[str, List[Tuple[int, str]]]:
        """获取订阅者信息
        
        Args:
            event_type: 事件类型，如果为None则返回所有事件
            
        Returns:
            订阅者信息
        """
        async with self._lock:
            if event_type:
                if event_type in self._subscribers:
                    return {event_type: [(p, pid) for p, pid, h in self._subscribers[event_type]]}
                return {event_type: []}
            return {
                et: [(p, pid) for p, pid, h in subs]
                for et, subs in self._subscribers.items()
            }
