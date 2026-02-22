# core/trust_manager.py
# 群组信任管理系统

import json
import os
from typing import Set, Dict, Any
from logger_config import get_logger

logger = get_logger("TrustManager")

TRUST_FILE_PATH = "data/trust.json"

class TrustManager:
    """群组信任管理器"""
    
    def __init__(self):
        self._trusted_groups: Set[str] = set()
        self._load_trusted_groups()
    
    def _load_trusted_groups(self):
        """从文件加载信任群组列表"""
        try:
            if os.path.exists(TRUST_FILE_PATH):
                with open(TRUST_FILE_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._trusted_groups = set(data.get("trusted_groups", []))
                logger.info(f"已加载 {len(self._trusted_groups)} 个信任群组")
            else:
                # 文件不存在，创建默认文件
                self._save_trusted_groups()
                logger.info("已创建默认信任群组文件")
        except Exception as e:
            logger.error(f"加载信任群组文件时出错: {e}")
            self._trusted_groups = set()
    
    def _save_trusted_groups(self):
        """保存信任群组列表到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(TRUST_FILE_PATH), exist_ok=True)
            
            data = {
                "trusted_groups": list(self._trusted_groups)
            }
            with open(TRUST_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("信任群组列表已保存")
        except Exception as e:
            logger.error(f"保存信任群组文件时出错: {e}")
    
    def add_trusted_group(self, group_id: str) -> bool:
        """添加信任群组
        
        Args:
            group_id: 群组ID
            
        Returns:
            bool: 是否添加成功
        """
        if group_id in self._trusted_groups:
            return False
        
        self._trusted_groups.add(group_id)
        self._save_trusted_groups()
        logger.info(f"群组 {group_id} 已添加到信任列表")
        return True
    
    def remove_trusted_group(self, group_id: str) -> bool:
        """移除信任群组
        
        Args:
            group_id: 群组ID
            
        Returns:
            bool: 是否移除成功
        """
        if group_id not in self._trusted_groups:
            return False
        
        self._trusted_groups.discard(group_id)
        self._save_trusted_groups()
        logger.info(f"群组 {group_id} 已从信任列表移除")
        return True
    
    def is_trusted_group(self, group_id: str) -> bool:
        """检查群组是否为信任群组
        
        Args:
            group_id: 群组ID
            
        Returns:
            bool: 是否为信任群组
        """
        # 实时检查文件以确保获取最新的信任状态
        self._load_trusted_groups()
        return group_id in self._trusted_groups
    
    def get_trusted_groups(self) -> Set[str]:
        """获取所有信任群组
        
        Returns:
            Set[str]: 信任群组集合
        """
        return self._trusted_groups.copy()

# 全局信任管理器实例
trust_manager = TrustManager()