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
        self._accounts_map: Dict[int, Dict[str, Any]] = {}  # 账号ID到账号信息的映射
        self._initialize_active_account()
        self._initialize_accounts_map()
    
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
    
    def _initialize_accounts_map(self):
        """初始化账号映射表"""
        accounts = self._config.get('accounts', [])
        for account in accounts:
            account_id = account.get('id')
            if account_id is not None:
                try:
                    self._accounts_map[int(account_id)] = account
                except (ValueError, TypeError):
                    logger.warning(f"账号ID '{account_id}' 无效，跳过")
    
    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """根据账号ID获取账号信息"""
        return self._accounts_map.get(account_id)
    
    def get_account_by_qq(self, bot_qq: str) -> Optional[Dict[str, Any]]:
        """根据QQ号获取账号信息"""
        for account in self._accounts_map.values():
            if str(account.get('bot_qq')) == str(bot_qq):
                return account
        return None
    
    def get_all_accounts(self) -> Dict[int, Dict[str, Any]]:
        """获取所有账号信息"""
        return self._accounts_map.copy()
    
    def is_parallel_mode(self) -> bool:
        """检查是否为并行模式"""
        return self._config.get('mode', 'fallback') == 'parallel'
    
    def is_parallel_pro_mode(self) -> bool:
        """检查是否为 Parallel Pro 模式"""
        return self._config.get('mode', 'fallback') == 'parallel-pro'
    
    def is_any_parallel_mode(self) -> bool:
        """检查是否为任意并行模式（parallel 或 parallel-pro）"""
        mode = self._config.get('mode', 'fallback')
        return mode in ('parallel', 'parallel-pro')

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

    def should_handle_message(self, event: dict, account_id: int = None, context=None) -> bool:
        """检查是否应该处理该消息
        
        Args:
            event: 事件数据
            account_id: 消息来源账号ID（parallel模式下使用）
            context: BotContext对象（parallel-pro模式下需要）
        """
        # 对于非消息类型的事件，总是处理
        post_type = event.get('post_type')
        if post_type not in ['message', 'notice', 'request']:
            return True
        
        # Parallel Pro 模式下，需要检查优先级
        if self.is_parallel_pro_mode():
            if account_id is None:
                logger.debug("Parallel Pro 模式: 无法获取账号ID，忽略消息")
                return False
            
            # 只处理群消息的优先级判断
            if post_type == 'message' and event.get('message_type') == 'group':
                group_id = event.get('group_id')
                if group_id and context and hasattr(context, 'multi_ws_manager'):
                    ws_manager = context.multi_ws_manager
                    if hasattr(ws_manager, 'is_highest_priority_in_group'):
                        # 检查群列表是否已缓存
                        accounts_in_group = ws_manager.get_accounts_in_group(str(group_id))
                        if not accounts_in_group:
                            # 群列表未缓存或该群不在缓存中，允许处理并记录警告
                            logger.warning(f"Parallel Pro 模式：群 {group_id} 的群列表未缓存，允许账号 {account_id} 处理消息")
                            return True
                        
                        is_highest = ws_manager.is_highest_priority_in_group(account_id, str(group_id))
                        if not is_highest:
                            logger.debug(f"Parallel Pro 模式：账号 {account_id} 在群 {group_id} 中有更高优先级的活跃账号，忽略消息")
                            return False
                        else:
                            logger.debug(f"Parallel Pro 模式：账号 {account_id} 是群 {group_id} 中最高优先级的活跃账号，处理消息")
            
            # 其他消息类型或无法判断时，允许处理
            return True
        
        # Parallel 模式下，处理所有来自已知账号的消息
        if self.is_parallel_mode():
            self_id = event.get('self_id')
            account = self.get_account_by_qq(str(self_id))
            if account:
                logger.debug(f"Parallel 模式: 处理账号 {self_id} 的{post_type}消息")
                return True
            else:
                logger.debug(f"Parallel 模式: 忽略未知账号 {self_id} 的{post_type}消息")
                return False
            
        # Fallback 模式下，检查是否来自当前活跃账号
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
    
    def get_account_config_value(self, account_id: int, key: str, default=None):
        """获取指定账号的配置值"""
        account = self.get_account_by_id(account_id)
        if account and key in account:
            return account[key]
        return default