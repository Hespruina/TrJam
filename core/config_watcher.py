# core/config_watcher.py
# 负责监控配置文件变化并在变化时重新加载配置

import os
import time
import threading
from logger_config import get_logger
from core.config_manager import reload_config
from typing import Callable, List

logger = get_logger("ConfigWatcher")

class ConfigWatcher:
    def __init__(self, config_files: List[str] = ["config.yml", "commands.yml"]):
        self.config_files = config_files
        self.file_stats = {}
        self.callbacks = []
        self.running = False
        self.thread = None
        
        # 初始化文件状态
        self._update_file_stats()
    
    def _update_file_stats(self):
        """更新文件状态信息"""
        for file_path in self.config_files:
            try:
                if os.path.exists(file_path):
                    stat = os.stat(file_path)
                    self.file_stats[file_path] = {
                        'mtime': stat.st_mtime,
                        'size': stat.st_size
                    }
                else:
                    self.file_stats[file_path] = None
            except Exception as e:
                logger.warning(f"无法获取文件 {file_path} 的状态: {e}")
                self.file_stats[file_path] = None
    
    def _check_file_changes(self):
        """检查文件是否有变化"""
        changed_files = []
        for file_path in self.config_files:
            try:
                if os.path.exists(file_path):
                    stat = os.stat(file_path)
                    current_stat = {
                        'mtime': stat.st_mtime,
                        'size': stat.st_size
                    }
                    
                    if (file_path not in self.file_stats or 
                        self.file_stats[file_path] != current_stat):
                        changed_files.append(file_path)
                        self.file_stats[file_path] = current_stat
                elif file_path in self.file_stats and self.file_stats[file_path] is not None:
                    # 文件已删除
                    changed_files.append(file_path)
                    self.file_stats[file_path] = None
            except Exception as e:
                logger.warning(f"检查文件 {file_path} 变化时出错: {e}")
        
        return changed_files
    
    def add_callback(self, callback: Callable[[List[str]], None]):
        """添加配置变化回调函数"""
        self.callbacks.append(callback)
    
    def _watch_loop(self):
        """监控循环"""
        while self.running:
            try:
                changed_files = self._check_file_changes()
                if changed_files:
                    logger.info(f"检测到配置文件变化: {changed_files}")
                    
                    # 尝试重新加载配置
                    try:
                        new_config = reload_config()
                        logger.info("配置文件重新加载成功")
                        
                        # 调用回调函数
                        for callback in self.callbacks:
                            try:
                                callback(changed_files)
                            except Exception as e:
                                logger.error(f"执行配置变化回调函数时出错: {e}")
                    except Exception as e:
                        logger.error(f"重新加载配置文件时出错: {e}")
                
                time.sleep(1)  # 每秒检查一次
            except Exception as e:
                logger.error(f"配置监控循环出错: {e}")
                time.sleep(5)  # 出错后等待5秒再继续
    
    def start(self):
        """启动监控"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._watch_loop, daemon=True)
            self.thread.start()
            logger.info("配置文件监控已启动")
    
    def stop(self):
        """停止监控"""
        if self.running:
            self.running = False
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            logger.info("配置文件监控已停止")

# 全局配置监控实例
config_watcher = ConfigWatcher()