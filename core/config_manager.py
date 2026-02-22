# core/config_manager.py
# 负责加载和（未来可能的）保存配置

import os
import yaml
from logger_config import get_logger, log_exception
from typing import Dict, Any

# 缓存已加载的配置
_cached_config = None

logger = get_logger("ConfigManager")

YAML_AVAILABLE = True
try:
    import yaml
except ImportError:
    logger.error("PyYAML库未安装，无法加载YAML配置文件。请运行 'pip install pyyaml' 安装。")
    YAML_AVAILABLE = False

def load_config() -> Dict[str, Any]:
    """从config.yml和commands.yml加载配置"""
    global _cached_config
    
    if not YAML_AVAILABLE:
        logger.error("YAML库不可用，无法加载配置文件。")
        return {}

    config = {}
    _load_config_file("config.yml", config)
    _load_config_file("commands.yml", config)

    # 标准化服务器配置
    if "servers" in config:
        for server_name, server in config["servers"].items():
            if "groups" in server:
                server["groups"] = {str(k): v for k, v in server["groups"].items()}
            if "zones" not in server:
                server["zones"] = []
            if "ips" not in server:
                server["ips"] = {}

    # 设置默认值
    config.setdefault("commands", {})
    config.setdefault("features", {})
    config.setdefault("command_categories", {})
    config.setdefault("error_messages", {})

    # 验证配置是否有效
    if _validate_config(config):
        # 更新缓存
        _cached_config = config
        return config
    else:
        logger.error("配置文件验证失败")
        return {}
        

def reload_config() -> Dict[str, Any]:
    """重新加载配置文件"""
    global _cached_config
    logger.info("开始重新加载配置文件")
    
    # 不需要清除缓存的日志级别，因为我们已经移除了缓存机制
    
    # 重新加载配置
    new_config = load_config()
    
    # 验证配置是否有效
    if _validate_config(new_config):
        _cached_config = new_config
        logger.info("配置文件重新加载完成并已生效")
        return new_config
    else:
        logger.warning("新配置文件验证失败，使用原有配置")
        return _cached_config if _cached_config else {}

def _validate_config(config: Dict[str, Any]) -> bool:
    """验证配置是否有效"""
    try:
        # 检查必需的配置项
        if "accounts" not in config or not isinstance(config["accounts"], list) or len(config["accounts"]) == 0:
            print("[ERROR] 配置文件缺少有效的 accounts 配置项")
            return False
            
        # 验证每个账号配置
        for account in config["accounts"]:
            if not isinstance(account, dict):
                print("[ERROR] 账号配置格式错误")
                return False
                
            if "ws_uri" not in account:
                print("[ERROR] 账号配置缺少 ws_uri 配置项")
                return False
                
            if "onebot_api_base" not in account:
                print("[ERROR] 账号配置缺少 onebot_api_base 配置项")
                return False
                
            if "access_token" not in account:
                print("[ERROR] 账号配置缺少 access_token 配置项")
                return False
                
            if "onebot_access_token" not in account:
                print("[ERROR] 账号配置缺少 onebot_access_token 配置项")
                return False
                
            if "bot_qq" not in account:
                print("[ERROR] 账号配置缺少 bot_qq 配置项")
                return False
                
        # 检查命令配置
        if "commands" not in config or not isinstance(config["commands"], dict):
            print("[ERROR] 配置文件缺少有效的 commands 配置项")
            return False
            
        # 检查服务器配置
        if "servers" in config:
            if not isinstance(config["servers"], dict):
                print("[ERROR] servers 配置项格式错误")
                return False
                
            for server_name, server in config["servers"].items():
                if not isinstance(server, dict):
                    print(f"[ERROR] 服务器 {server_name} 配置格式错误")
                    return False
                    
        return True
    except Exception as e:
        logger.error(f"配置验证过程中出错: {e}")
        return False

def _load_config_file(filename: str, config: Dict[str, Any]):
    """加载单个配置文件"""
    try:
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)
        if not os.path.exists(filepath):
            logger.error(f"{filepath}文件不存在")
            return

        with open(filepath, "r", encoding="utf-8") as f:
            file_data = yaml.safe_load(f)
            if file_data:
                config.update(file_data)
    except Exception as e:
        log_exception(logger, f"加载{filename}异常", e)

# 添加一个函数用于获取特定模块的配置
def get_module_config(config: Dict[str, Any], module_name: str) -> Dict[str, Any]:
    """获取特定模块的配置"""
    return config.get(module_name, {})