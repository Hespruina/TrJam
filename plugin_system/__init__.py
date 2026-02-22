# plugin_system/__init__.py
# 插件系统入口

from plugin_system.plugin_manager import PluginManager
from plugin_system.plugin_base import PluginBase, PluginContext
from plugin_system.event_bus import EventBus
from plugin_system.service_registry import ServiceRegistry
from plugin_system.exceptions import (
    PluginError,
    PluginNotFoundError,
    PluginLoadError,
    PluginDependencyError,
    PluginPermissionError
)

__version__ = "1.0.0"

__all__ = [
    'PluginManager',
    'PluginBase',
    'PluginContext',
    'EventBus',
    'ServiceRegistry',
    'PluginError',
    'PluginNotFoundError',
    'PluginLoadError',
    'PluginDependencyError',
    'PluginPermissionError',
]
