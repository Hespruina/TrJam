import argparse
import logging
from typing import Dict, Optional

from logger_config import get_logger

logger = get_logger("SubBotUtils")

def parse_subbot_args() -> Dict[str, Optional[str]]:
    """解析子机器人启动参数"""
    parser = argparse.ArgumentParser(description="子机器人启动参数")
    
    # 添加WebSocket端口参数
    parser.add_argument(
        "--ws_port",
        type=int,
        help="WebSocket转发器的端口号"
    )
    
    # 添加认证token参数
    parser.add_argument(
        "--token",
        type=str,
        help="子机器人的唯一认证token"
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # 验证必要参数
    if not args.ws_port:
        logger.error("缺少必要参数: --ws_port")
        return {}
    
    if not args.token:
        logger.error("缺少必要参数: --token")
        return {}
    
    # 返回解析结果
    return {
        "ws_port": args.ws_port,
        "token": args.token
    }

def validate_subbot_config(config: Dict) -> bool:
    """验证子机器人配置"""
    required_keys = ["ws_port", "token"]
    
    for key in required_keys:
        if key not in config:
            logger.error(f"配置缺少必要键: {key}")
            return False
    
    # 验证端口范围
    if config["ws_port"] < 1 or config["ws_port"] > 65535:
        logger.error(f"无效的端口号: {config['ws_port']}")
        return False
    
    # 验证token长度
    if len(config["token"]) < 16:
        logger.warning(f"token长度较短，建议至少16个字符")
    
    return True

def get_subbot_ws_url(port: int) -> str:
    """获取子机器人WebSocket连接URL"""
    return f"ws://127.0.0.1:{port}"

def create_subbot_connection_config(port: int, token: str) -> Dict:
    """创建子机器人连接配置"""
    return {
        "ws_url": get_subbot_ws_url(port),
        "token": token,
        "reconnect_interval": 5,  # 重连间隔（秒）
        "max_reconnect_attempts": 10  # 最大重连次数
    }