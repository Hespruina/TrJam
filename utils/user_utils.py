# utils/user_utils.py
# 提供获取用户昵称等与用户相关的工具函数

from logger_config import get_logger
from core.bot_context import BotContext

logger = get_logger("UserUtils")

async def get_user_nickname(context: BotContext, user_id: str) -> str:
    """获取用户昵称"""
    try:
        from utils.api_utils import call_onebot_api
        info_data = await call_onebot_api(
            context, 'get_stranger_info',
            {'user_id': int(user_id), 'no_cache': True}
        )
        if info_data and info_data.get("success") and info_data["data"].get('status') == 'ok':
            return info_data["data"].get('data', {}).get('nickname', str(user_id))
    except Exception as e:
        logger.error(f"获取用户 {user_id} 昵称失败: {e}")
    return str(user_id)