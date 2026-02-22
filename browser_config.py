import os
import yaml
from typing import Dict, Any

# 浏览器配置文件路径
BROWSER_CONFIG_FILE = "browser_config.yml"

# 默认浏览器配置
DEFAULT_BROWSER_CONFIG = {
    "use_system_browser": True,  # 是否使用系统浏览器
    "preferred_browser": "msedge",  # 首选浏览器: msedge, chrome, firefox
    "fallback_to_builtin": True,  # 当系统浏览器不可用时是否回退到内置浏览器
    "headless": True,  # 是否无头模式运行
    "performance_optimization": {
        "disable_gpu": True,
        "disable_extensions": True,
        "memory_limit_mb": 512,
        "dev_shm_usage": False
    }
}

def load_browser_config() -> Dict[str, Any]:
    """
    加载浏览器配置
    如果配置文件不存在，则创建默认配置文件并返回默认配置
    """
    if os.path.exists(BROWSER_CONFIG_FILE):
        try:
            with open(BROWSER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                # 合并默认配置，确保所有必需的键都存在
                merged_config = DEFAULT_BROWSER_CONFIG.copy()
                merged_config.update(config or {})
                return merged_config
        except Exception as e:
            print(f"读取浏览器配置文件失败: {e}，使用默认配置")
            return DEFAULT_BROWSER_CONFIG
    else:
        # 创建默认配置文件
        save_browser_config(DEFAULT_BROWSER_CONFIG)
        return DEFAULT_BROWSER_CONFIG

def save_browser_config(config: Dict[str, Any]):
    """
    保存浏览器配置到文件
    """
    try:
        with open(BROWSER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        print(f"浏览器配置已保存到 {BROWSER_CONFIG_FILE}")
    except Exception as e:
        print(f"保存浏览器配置文件失败: {e}")

def get_browser_manager_config():
    """
    获取浏览器管理器配置
    """
    config = load_browser_config()
    return {
        "use_system_browser": config.get("use_system_browser", True),
        "browser_type": config.get("preferred_browser", "msedge"),
        "headless": config.get("headless", True)
    }

# 导出配置加载函数
__all__ = ['load_browser_config', 'save_browser_config', 'get_browser_manager_config']