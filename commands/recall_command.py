# commands/recall_command.py
# 重构后的撤回命令

import json
import time
from datetime import datetime
from logger_config import get_logger
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.message_sender import MessageBuilder

logger = get_logger("RecallCommand")

async def handle_recall(context: BotContext, args: list, user_id: str, group_id: str, server_name: str = None, command: str = None, raw_message: list = None, websocket = None, message_id: str = None, sender_role: str = None, **kwargs) -> str:
    """处理撤回功能
    
    :param context: 机器人上下文
    :param args: 命令参数列表
    :param user_id: 用户ID
    :param group_id: 群组ID
    :param server_name: 服务器名称
    :param command: 命令名称
    :param raw_message: 原始消息内容
    :param websocket: WebSocket连接
    :param message_id: 消息ID
    :param sender_role: 发送者角色
    :param kwargs: 其他参数
    :return: 命令执行结果
    """
    # 允许处理中文命令"撤"、"撤回"或英文命令"recall"
    if command not in ["撤", "撤回", "recall"]:
        return None

    # 从上下文中获取配置
    features_config = {
        "enabled": True, # 假设默认启用
        "permission": "Admin",
        "time_limit": 0, # 完全移除撤回时间限制
        "allow_others": True,  # 允许管理员撤回他人消息
        "allow_self": True
    }

    if not features_config.get("enabled", False):
        return None

    replied_message_id = None
    if isinstance(raw_message, list):
        for segment in raw_message:
            if segment.get('type') == 'reply':
                replied_message_id = segment.get('data', {}).get('id')
                break

    if not replied_message_id:
        return None

    required_permission = features_config.get("permission", "Admin")
    perm_mapping = {"User": 0, "Admin": 1, "Root": 2}
    required_level = perm_mapping.get(required_permission, 1)
    from commands.permission_manager import check_permission
    user_level = check_permission(context, user_id, group_id, sender_role)

    if user_level < required_level:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ⚠️ 需要{required_permission}权限才能撤回消息")
        await builder.send()
        return None

    msg_data = await call_onebot_api(
        context, 'get_msg', 
        {'message_id': replied_message_id}
    )
    if not msg_data or not msg_data.get("success") or msg_data["data"].get('status') != 'ok':
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 无法获取被引用的消息内容")
        await builder.send()
        return None

    msg_time = msg_data["data"]['data'].get('time', 0)
    current_time = int(time.time())
    time_limit = features_config.get("time_limit", 0) # 默认值也设为0，确保完全移除时间限制
    if time_limit > 0 and (current_time - msg_time > time_limit):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ⚠️ 消息已超过撤回时限（{time_limit}秒）")
        await builder.send()
        return None

    msg_sender = str(msg_data["data"]['data'].get('sender', {}).get('user_id', ''))
    if msg_sender != str(user_id):
        # 只有Admin和Root权限的用户可以撤回任何消息
        # 对于普通用户，仍然限制只能撤回自己的消息
        if user_level < 1:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(" ⚠️ 你只能撤回自己发送的消息")
            await builder.send()
            return None
    else:
        if not features_config.get("allow_self", True):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(" ⚠️ 你不能撤回自己发送的消息")
            await builder.send()
            return None

    # 先尝试撤回目标消息
    result = await call_onebot_api(
        context, 'delete_msg', 
        {'message_id': replied_message_id}
    )
    
    # 如果目标消息撤回成功，再尝试撤回当前命令消息
    if result and result.get("success") and result["data"].get('status') == 'ok':
        # 尝试撤回当前的recall命令消息
        if message_id:
            try:
                await call_onebot_api(
                    context, 'delete_msg', 
                    {'message_id': message_id}
                )
                logger.info(f"已尝试撤回recall命令消息，ID: {message_id}")
            except Exception as e:
                logger.error(f"撤回recall命令消息失败: {e}")
        # 根据需求，撤回成功后不发送提示消息
        pass
    else:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 撤回消息失败")
        await builder.send()
    return None

