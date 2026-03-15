# core/bot_context/account_manager.py
# 负责管理账号相关的逻辑，包括账号切换、消息处理判断等

from typing import Dict, Optional, List, Any
from logger_config import get_logger

logger = get_logger("AccountManager")

class AccountManager:
    """管理机器人账号相关的逻辑"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.accounts = {acc['id']: acc for acc in config.get('accounts', []) if 'id' in acc}
        self.active_account: Optional[Dict[str, Any]] = None
        logger.debug(f"AccountManager 初始化完成，加载了 {len(self.accounts)} 个账号")
    
    def get_config_value(self, key: str, default=None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
    
    def get_all_accounts(self) -> Dict[int, Dict[str, Any]]:
        """获取所有账号配置"""
        return self.accounts.copy()
    
    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """根据账号 ID 获取账号配置"""
        return self.accounts.get(account_id)
    
    def get_account_by_qq(self, bot_qq: str) -> Optional[Dict[str, Any]]:
        """根据 QQ 号获取账号配置"""
        for account in self.accounts.values():
            if str(account.get('bot_qq')) == str(bot_qq):
                return account
        return None
    
    def get_active_account(self) -> Optional[Dict[str, Any]]:
        """获取当前活跃账号"""
        return self.active_account
    
    async def set_active_account(self, account_info: Dict[str, Any]):
        """设置当前活跃账号"""
        self.active_account = account_info
        logger.debug(f"设置活跃账号为：{account_info.get('id')}")
    
    def is_parallel_mode(self) -> bool:
        """检查是否为并行模式"""
        return self.get_config_value('mode', 'fallback') == 'parallel'
    
    def is_parallel_pro_mode(self) -> bool:
        """检查是否为并行专业模式"""
        return self.get_config_value('mode', 'fallback') == 'parallel-pro'
    
    def should_handle_message(self, event: dict, account_id: int = None, context=None) -> bool:
        """检查是否应该处理该消息
        
        Args:
            event: 事件数据
            account_id: 消息来源账号 ID（parallel 模式下使用）
            context: BotContext 对象（parallel-pro 模式下需要）
        """
        # 对于非消息类型的事件，总是处理
        post_type = event.get('post_type')
        
        # request 类型（加群请求、邀请请求等）应该总是处理，不受优先级影响
        if post_type == 'request':
            logger.info(f"处理 request 类型事件：{event.get('request_type', 'unknown')}")
            return True
        
        # notice 类型也总是处理
        if post_type == 'notice':
            logger.info(f"处理 notice 类型事件：{event.get('notice_type', 'unknown')}")
            return True
        
        # 对于 meta_event 等其他类型，也总是处理
        if post_type not in ['message']:
            return True
        
        # Parallel Pro 模式下，群消息需要检查优先级
        if self.is_parallel_pro_mode():
            if account_id is None:
                # 尝试从事件中获取 self_id 来推断账号
                self_id = event.get('self_id')
                if self_id:
                    account = self.get_account_by_qq(str(self_id))
                    if account:
                        account_id = account.get('id')
                        logger.debug(f"从 self_id {self_id} 推断出账号 ID {account_id}")
                
                if account_id is None:
                    logger.warning(f"Parallel Pro 模式：无法获取账号 ID，但允许处理{post_type}消息")
                    # 即使无法获取账号 ID，也允许处理消息，避免完全忽略消息
                    return True
            
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
            
            # 其他消息类型（私聊消息等）允许处理
            return True
        
        # Parallel 模式下，处理所有来自已知账号的消息
        if self.is_parallel_mode():
            self_id = event.get('self_id')
            account = self.get_account_by_qq(str(self_id))
            if account:
                logger.debug(f"Parallel 模式：处理账号 {self_id} 的{post_type}消息")
                return True
            else:
                logger.debug(f"Parallel 模式：忽略未知账号 {self_id} 的{post_type}消息")
                return False
            
        # Fallback 模式下，检查是否来自当前活跃账号
        self_id = event.get('self_id')
        active_account = self.get_active_account()
        if active_account:
            active_qq = active_account.get('bot_qq')
            if str(self_id) != str(active_qq):
                logger.debug(f"忽略非活跃账号 {self_id} 的{post_type}消息，当前活跃账号：{active_qq}")
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
