# commands/mute_command.py
# 处理 /mute, /unmute, /kick 命令

import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_utils import parse_at_or_qq
from utils.api_utils import call_onebot_api

logger = get_logger("MuteCommand")

async def handle_mute_command(context: BotContext, args: list, user_id: str, group_id: str, command: str, **kwargs) -> str:
    """处理 /mute, /unmute, /kick 命令。"""
    action = command
    if not args:
        if action == "mute":
            return "❌ 参数错误，格式：/mute @用户或QQ号 [时长(如1m,1h,1d)]"
        else:
            return f"❌ 参数错误，格式：/{action} @用户或QQ号"

    target_user_id, duration_args = parse_at_or_qq(args)
    if not target_user_id:
        return "❌ 无效的 QQ 号或 @ 格式"

    if target_user_id == str(user_id):
        return f"⚠️ 你不能{action}自己"

    if target_user_id == str(context.get_config_value("bot_qq", "")):
        return f"⚠️ 你不能{action}机器人"

    duration_seconds = 0
    if action == "mute":
        if duration_args:
            duration_str = duration_args[0]
            multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            unit = duration_str[-1].lower()
            if unit in multipliers:
                try:
                    value = int(duration_str[:-1])
                    duration_seconds = value * multipliers[unit]
                    if duration_seconds <= 0:
                        return "❌ 时长必须是正数"
                except ValueError:
                    return "❌ 无效的时长格式，例如: 30s, 5m, 1h, 2d"
            else:
                 return "❌ 无效的时长单位，支持 s(秒), m(分), h(时), d(天)"

    api_action = ""
    api_params = {"group_id": int(group_id), "user_id": int(target_user_id)}
    if action == "mute":
        api_action = "set_group_ban"
        api_params["duration"] = duration_seconds
        action_cn = "禁言"
    elif action == "unmute":
        api_action = "set_group_ban"
        api_params["duration"] = 0
        action_cn = "解除禁言"
    elif action == "kick":
        api_action = "set_group_kick"
        api_params["reject_add_request"] = False
        action_cn = "踢出"

    try:
        response = await call_onebot_api(context, api_action, api_params)
        if response and response.get('success') and response.get('data', {}).get('status') == 'ok':
            logger.info(f"已成功{action_cn}用户 {target_user_id}，群: {group_id}")
            duration_text = ""
            if action == "mute":
                if duration_seconds == 0:
                    duration_text = " (永久)"
                else:
                    duration_text = f" ({duration_seconds}秒)"
            return f"✅ 已{action_cn}用户 {target_user_id}{duration_text}"
        else:
            failure_reason = "未知原因"
            if response:
                if not response.get('success'):
                    failure_reason = response.get('error', 'API调用失败')
                else:
                    failure_reason = f"业务状态非成功: {response.get('data', {}).get('status', '未知')}"
            logger.error(f"{action_cn}用户失败，群: {group_id}，用户: {target_user_id}，原因: {failure_reason}")
            return f"🛑 执行{action_cn}时发生错误: {failure_reason}"
    except Exception as e:
        logger.error(f"发送 {action_cn} 请求时发生异常: {e}")
        return f"🛑 执行{action_cn}时发生错误: {e}"