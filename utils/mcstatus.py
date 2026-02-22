#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import socket
import argparse
from mcstatus import JavaServer
from typing import Dict, List, Optional, Union, Any


def clean_description(desc: Any) -> str:
    """清理 Minecraft 服务器的描述文本（MOTD）
    
    Args:
        desc: 服务器描述文本，可以是字符串、字典或列表格式
    
    Returns:
        清理后的纯文本描述
    """
    if isinstance(desc, str):
        return desc
    elif isinstance(desc, dict):
        def extract_text(obj: Any) -> str:
            if isinstance(obj, str):
                return obj
            elif isinstance(obj, dict):
                text = obj.get("text", "")
                extra = obj.get("extra", [])
                if isinstance(extra, list):
                    for e in extra:
                        text += extract_text(e)
                return text
            elif isinstance(obj, list):
                return "".join(extract_text(item) for item in obj)
            return ""
        return extract_text(desc)
    else:
        return str(desc)


class MinecraftServerInfo:
    """Minecraft 服务器信息类"""
    def __init__(self, address: str, timeout: float = 5.0):
        """
        Args:
            address: 服务器地址（格式可以是 IP:端口 或 域名）
            timeout: 连接超时时间（秒）
        """
        self.address = address
        self.timeout = timeout
        self.server = None
        self.status = None
        self.error = None
        
        # 尝试连接服务器
        self._connect()
    
    def _connect(self) -> None:
        """连接到 Minecraft 服务器"""
        try:
            # 设置全局 socket 超时（影响 DNS 和连接）
            socket.setdefaulttimeout(self.timeout)
            self.server = JavaServer.lookup(self.address)
            self.status = self.server.status()  # 旧版不支持 timeout 参数
        except Exception as e:
            self.error = str(e)
        finally:
            # 恢复默认超时
            socket.setdefaulttimeout(None)
    
    @property
    def is_online(self) -> bool:
        """服务器是否在线"""
        return self.status is not None and self.error is None
    
    @property
    def motd(self) -> str:
        """获取服务器的 MOTD（服务器描述）"""
        if not self.is_online:
            return "服务器离线"
        return clean_description(self.status.description)
    
    @property
    def version(self) -> str:
        """获取服务器版本"""
        if not self.is_online:
            return "未知"
        return self.status.version.name
    
    @property
    def players_online(self) -> int:
        """获取当前在线人数"""
        if not self.is_online:
            return 0
        return self.status.players.online
    
    @property
    def players_max(self) -> int:
        """获取最大在线人数"""
        if not self.is_online:
            return 0
        return self.status.players.max
    
    @property
    def player_sample(self) -> List[Dict[str, str]]:
        """获取在线玩家样本列表"""
        if not self.is_online or not self.status.players.sample:
            return []
        return [{'name': player.name, 'id': player.id} for player in self.status.players.sample]
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取完整的服务器信息
        
        Returns:
            包含服务器所有信息的字典
        """
        if not self.is_online:
            return {
                'status': 'offline',
                'error': self.error or '连接失败'
            }
        
        return {
            'status': 'online',
            'address': self.address,
            'motd': self.motd,
            'version': self.version,
            'players_online': self.players_online,
            'players_max': self.players_max,
            'player_sample': self.player_sample
        }
    
    def get_formatted_info(self) -> str:
        """获取格式化的服务器信息文本
        
        Returns:
            格式化的服务器信息文本
        """
        if not self.is_online:
            return f"❌ 查询失败: {self.error or '连接失败'}"
        
        lines = [
            "=" * 60,
            "Minecraft 服务器信息",
            "=" * 60,
            f"MOTD: {self.motd}",
            f"版本: {self.version}",
            f"在线人数: {self.players_online} / {self.players_max}"
        ]
        
        if self.player_sample:
            lines.append(f"\n在线玩家列表 ({len(self.player_sample)} 人):")
            for player in self.player_sample:
                lines.append(f"  - {player['name']}")
        else:
            lines.append("\n⚠️  服务器未提供在线玩家列表")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# 兼容旧版的函数

def get_minecraft_server_info(address: str, timeout: float = 5.0) -> Dict[str, Any]:
    """获取 Minecraft 服务器信息
    
    Args:
        address: 服务器地址
        timeout: 连接超时时间（秒）
        
    Returns:
        包含服务器信息的字典
    """
    server = MinecraftServerInfo(address, timeout)
    return server.get_server_info()


# 命令行工具支持

def main():
    parser = argparse.ArgumentParser(description="获取 Minecraft 服务器信息（兼容旧版 mcstatus）")
    parser.add_argument("address", help="服务器地址")
    parser.add_argument("-t", "--timeout", type=float, default=5.0, help="连接超时（秒）")
    args = parser.parse_args()

    server = MinecraftServerInfo(args.address, args.timeout)
    print(server.get_formatted_info())


if __name__ == "__main__":
    main()