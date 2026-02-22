# plugin_system/logger_factory.py
# 插件日志工厂

import logging
from typing import Optional


class LoggerFactory:
    """插件日志工厂"""
    
    _initialized = False
    _base_logger: Optional[logging.Logger] = None
    
    @classmethod
    def get_logger(cls, plugin_id: str) -> logging.Logger:
        """获取插件专用日志器
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            日志器实例
        """
        logger_name = f"Plugin.{plugin_id}"
        logger = logging.getLogger(logger_name)
        
        # 避免重复添加处理器
        if not logger.handlers:
            logger.setLevel(logging.DEBUG)
            
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    @classmethod
    def set_level(cls, level: int):
        """设置所有插件日志器的日志级别
        
        Args:
            level: 日志级别
        """
        for logger in logging.Logger.manager.loggerDict.values():
            if isinstance(logger, logging.Logger) and logger.name.startswith("Plugin."):
                logger.setLevel(level)
