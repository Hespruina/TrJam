# core/bot_context/__init__.py
# 负责管理全局状态（原全局变量），如配置和WebSocket连接

from typing import Optional, Dict, Any, Callable
from logger_config import get_logger
from core.bot_context.account_manager import AccountManager
from core.bot_context.message_sender import MessageSender
from core.bot_context.config_manager import ConfigManager

logger = get_logger("BotContext")

class BotContext:
    """机器人的核心上下文，用于管理配置和WebSocket连接等全局状态。"""

    def __init__(self, config: Dict[str, Any]):
        self._account_manager = AccountManager(config)
        self._message_sender = MessageSender()
        self._message_sender.set_context(self)  # 设置上下文引用
        self._config_manager = ConfigManager(config)

    @property
    def config(self) -> Dict[str, Any]:
        return self._config_manager.get_config()

    @property
    def websocket(self):
        return self._message_sender.websocket

    async def set_websocket(self, ws):
        """设置当前的WebSocket连接。"""
        await self._message_sender.set_websocket(ws)

    async def set_active_account(self, account_info: Dict[str, Any]):
        """设置当前活跃账号信息。"""
        old_account = self.get_active_account()
        await self._account_manager.set_active_account(account_info)
        
        # 触发账号切换事件，通知插件系统
        if hasattr(self, 'plugin_manager'):
            try:
                await self.plugin_manager.handle_account_switch(old_account, account_info)
                logger.info("账号切换事件已通知插件系统")
            except Exception as e:
                logger.error(f"通知插件系统账号切换失败: {e}")

    def get_active_account(self) -> Optional[Dict[str, Any]]:
        """获取当前活跃账号信息。"""
        return self._account_manager.get_active_account()

    def get_config_value(self, key: str, default=None):
        """安全地获取配置值。"""
        return self._account_manager.get_config_value(key, default)

    def should_handle_message(self, event: dict) -> bool:
        """检查是否应该处理该消息（基于当前活跃账号）"""
        return self._account_manager.should_handle_message(event)

    async def send_group_message(self, group_id: str, message: list, callback: Optional[Callable] = None) -> Optional[str]:
        """发送群消息并可选注册回调函数"""
        return await self._message_sender.send_group_message(group_id, message, callback)
    
    async def send_private_message(self, user_id: str, message: list, callback: Optional[Callable] = None) -> Optional[str]:
        """发送私聊消息并可选注册回调函数"""
        return await self._message_sender.send_private_message(user_id, message, callback)

    def register_message_callback(self, echo: str, callback: Callable):
        """注册消息回调函数"""
        self._message_sender.register_message_callback(echo, callback)

    def handle_message_response(self, response: dict):
        """处理消息响应"""
        self._message_sender.handle_message_response(response)

    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """获取指定服务器的配置。"""
        return self._config_manager.get_server_config(server_name)

    def get_group_config(self, group_id: str) -> Optional[Dict[str, Any]]:
        """获取指定群组的配置。"""
        return self._config_manager.get_group_config(group_id)
