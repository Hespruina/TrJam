import socket
import random
from typing import Optional

class PortManager:
    """端口管理器，负责自动分配可用端口并避免冲突"""
    
    def __init__(self):
        self.used_ports = set()
        self.min_port = 10000
        self.max_port = 65535
    
    def is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        if port in self.used_ports:
            return False
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('127.0.0.1', port))
            return True
        except:
            return False
    
    def get_available_port(self) -> Optional[int]:
        """获取一个可用的端口"""
        # 尝试随机端口
        for _ in range(100):
            port = random.randint(self.min_port, self.max_port)
            if self.is_port_available(port):
                self.used_ports.add(port)
                return port
        
        # 如果随机失败，尝试顺序查找
        for port in range(self.min_port, self.max_port + 1):
            if self.is_port_available(port):
                self.used_ports.add(port)
                return port
        
        return None
    
    def release_port(self, port: int) -> None:
        """释放端口"""
        if port in self.used_ports:
            self.used_ports.remove(port)
    
    def get_used_ports(self) -> set:
        """获取已使用的端口集合"""
        return self.used_ports.copy()

# 创建全局端口管理器实例
port_manager = PortManager()