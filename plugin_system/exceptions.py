# plugin_system/exceptions.py
# 插件系统自定义异常


class PluginError(Exception):
    """插件基础异常"""
    pass


class PluginNotFoundError(PluginError):
    """插件未找到异常"""
    pass


class PluginLoadError(PluginError):
    """插件加载失败异常"""
    pass


class PluginDependencyError(PluginError):
    """插件依赖错误异常"""
    pass


class PluginPermissionError(PluginError):
    """插件权限错误异常"""
    pass
