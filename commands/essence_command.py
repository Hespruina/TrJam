# commands/essence_command.py
# 实现精华消息命令

import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.message_sender import MessageBuilder, CommandResponse

logger = get_logger("EssenceCommand")

async def handle_essence_command(context: BotContext, args: list, user_id: str, group_id: str, nickname: str, sender_role: str = "member", **kwargs) -> CommandResponse:
    """处理精华消息命令"""
    
    # 检查用户权限（管理员、群主、admin或root）
    user_level = _check_user_permission(context, user_id, group_id, sender_role)
    
    if user_level < 1:  # 需要至少是管理员权限
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 权限不足，仅群管理员、群主、Admin或Root用户可以设置精华消息")
        await builder.send()
        return CommandResponse.none()
    
    # 获取原始消息内容以检查是否有引用消息
    raw_message = kwargs.get('raw_message', [])
    
    # 尝试从引用消息中获取消息ID
    message_id = None
    if isinstance(raw_message, list):
        for segment in raw_message:
            if segment.get('type') == 'reply':
                message_id = segment.get('data', {}).get('id')
                break
    
    # 如果没有引用消息
    if not message_id:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ⚠️ 请引用一条消息后再使用此命令")
        await builder.send()
        return CommandResponse.none()
    
    # 调用API设置精华消息
    result = await call_onebot_api(
        context=context,
        action="set_essence_msg",
        params={
            "message_id": message_id
        }
    )
    
    # 处理API响应
    builder = MessageBuilder(context)
    builder.set_group_id(group_id)
    builder.set_user_id(user_id)
    builder.add_at()
    
    if result and result.get('success'):
        builder.add_text(" ✅ 已将该消息设为精华消息")
    else:
        error_msg = result.get('error', '未知错误') if result else 'API调用失败'
        builder.add_text(f" ❌ 设置精华消息失败: {error_msg}")
    
    await builder.send()
    return CommandResponse.none()

def _check_user_permission(context: BotContext, user_id: str, group_id: str, sender_role: str) -> int:
    """检查用户权限级别
    返回值:
    0 - 普通用户
    1 - 管理员/群主/Admin
    2 - Root用户
    """
    # 检查是否为Root用户
    root_user_id = context.get_config_value("Root_user")
    if root_user_id and str(user_id) == str(root_user_id):
        return 2
    
    # 检查是否为群主或管理员
    if sender_role in ["owner", "admin"]:
        return 1
    
    # 检查是否为群组Admin
    group_config = context.get_group_config(str(group_id))
    if group_config and "Admin" in group_config:
        admin_list = group_config["Admin"]
        if str(user_id) in admin_list:
            return 1
    
    # 普通用户
    return 0