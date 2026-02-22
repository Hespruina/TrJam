# core/bot_context/config_manager.py
# 配置管理功能

import json
import os
from typing import Optional, Dict, Any
from logger_config import get_logger

logger = get_logger("BotContextConfigManager")

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self._config = config

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._config

    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """获取指定服务器的配置。"""
        return self._config.get("servers", {}).get(server_name)

    def get_group_config(self, group_id: str) -> Optional[Dict[str, Any]]:
        """获取指定群组的配置。"""
        # 首先从config.yml中获取基础配置
        for server in self._config.get("servers", {}).values():
            if group_id in server.get("groups", {}):
                group_config = server["groups"][group_id].copy()  # 复制基础配置
                
                # 加载群组特定的配置文件（如果存在）
                config_file = f"data/group_config/{group_id}.json"
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            additional_config = json.load(f)
                            # 合并配置，群组特定配置优先
                            group_config.update(additional_config)
                    except Exception as e:
                        logger.warning(f"加载群组配置文件 {config_file} 时出错: {e}")
                
                return group_config
        
        # 如果在config.yml中没有找到群组配置，检查插件配置中的群组
        # 插件配置也存储在config["servers"]中，所以不需要额外处理
        
        # 如果在所有配置中都没有找到群组配置，但仍可能存在群组特定配置文件
        config_file = f"data/group_config/{group_id}.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    group_config = json.load(f)
                return group_config
            except Exception as e:
                logger.warning(f"加载群组配置文件 {config_file} 时出错: {e}")
        
        return None