# core/bot_context/account_manager.py
# 账号管理功能

import asyncio
from typing import Optional, Dict, Any
from logger_config import get_logger

logger = get_logger("BotContextAccountManager")

class AccountManager:
    """账号管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._active_account = None
        self._lock = asyncio.Lock()
        self._initialize_active_account()
    
    def _initialize_active_account(self):
        """初始化活跃账号信息"""
        accounts = self._config.get('accounts', [])
        if accounts:
            # 默认使用第一个账号作为活跃账号
            primary_account = accounts[0]
            self._active_account = {
                'id': primary_account.get('id'),
                'bot_qq': primary_account.get('bot_qq'),
                'onebot_api_base': primary_account.get('onebot_api_base'),
                'onebot_access_token': primary_account.get('onebot_access_token')
            }

    async def set_active_account(self, account_info: Dict[str, Any]):
        """设置当前活跃账号信息。"""
        async with self._lock:
            self._active_account = account_info
            logger.info(f"切换到账号: {account_info.get('id')} (QQ: {account_info.get('bot_qq')})")

    def get_active_account(self) -> Optional[Dict[str, Any]]:
        """获取当前活跃账号信息。"""
        return self._active_account

    def get_config_value(self, key: str, default=None):
        """安全地获取配置值。"""
        # 如果是获取bot_qq、onebot_api_base等账号相关配置，优先从活跃账号获取
        if key in ['bot_qq', 'onebot_api_base', 'onebot_access_token'] and self._active_account:
            if key in self._active_account:
                return self._active_account[key]
        
        return self._config.get(key, default)

    def should_handle_message(self, event: dict) -> bool:
        """检查是否应该处理该消息（基于当前活跃账号）"""
        # 对于非消息类型的事件，总是处理
        post_type = event.get('post_type')
        if post_type not in ['message', 'notice', 'request']:
            return True
            
        # 对于消息类型事件，检查是否来自当前活跃账号
        self_id = event.get('self_id')
        active_account = self.get_active_account()
        if active_account:
            active_qq = active_account.get('bot_qq')
            if str(self_id) != str(active_qq):
                logger.debug(f"忽略非活跃账号 {self_id} 的{post_type}消息，当前活跃账号: {active_qq}")
                return False
            else:
                logger.debug(f"处理活跃账号 {self_id} 的{post_type}消息")
                return True
        else:
            # 如果没有活跃账号信息，处理所有消息
            logger.debug("未获取到活跃账号信息，处理所有消息")
            return True