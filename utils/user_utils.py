# utils/user_utils.py
# 提供获取用户昵称等与用户相关的工具函数

from logger_config import get_logger
from core.bot_context import BotContext

logger = get_logger("UserUtils")

async def get_user_nickname(context: BotContext, user_id: str, account_id: int = None) -> str:
    """获取用户昵称
    
    Args:
        context: BotContext 对象
        user_id: 用户 QQ 号
        account_id: 指定账号 ID（parallel-pro 模式下使用），None 则使用当前活跃账号
    """
    try:
        from utils.api_utils import call_onebot_api
        info_data = await call_onebot_api(
            context, 'get_stranger_info',
            {'user_id': int(user_id), 'no_cache': True},
            account_id=account_id
        )
        if info_data and info_data.get("success") and info_data["data"].get('status') == 'ok':
            return info_data["data"].get('data', {}).get('nickname', str(user_id))
    except Exception as e:
        logger.error(f"获取用户 {user_id} 昵称失败：{e}")
    return str(user_id)