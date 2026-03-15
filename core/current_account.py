# core/current_account.py
# 用于存储当前消息处理的账号ID（parallel模式下使用）

import contextvars
from typing import Optional

# 创建上下文变量来存储当前账号ID
current_account_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar('current_account_id', default=None)

def set_current_account_id(account_id: int) -> None:
    """设置当前账号ID"""
    current_account_id.set(account_id)

def get_current_account_id() -> Optional[int]:
    """获取当前账号ID"""
    return current_account_id.get()

def clear_current_account_id() -> None:
    """清除当前账号ID"""
    current_account_id.set(None)
