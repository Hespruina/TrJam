# commands/qqinfo_command.py
# 处理 /qqinfo 命令

import json
from datetime import datetime
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_utils import parse_at_or_qq
from utils.api_utils import call_onebot_api

logger = get_logger("QqinfoCommand")

async def handle_qqinfo_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> str:
    """处理 /qqinfo 命令。"""
    if not args:
        return "❌ 请 @ 一个用户或提供 QQ 号"

    target_user_id, _ = parse_at_or_qq(args)
    if not target_user_id:
        return "❌ 无效的 QQ 号或 @ 格式"

    try:
        info_data = await call_onebot_api(
            context, 'get_stranger_info',
            {'user_id': int(target_user_id), 'no_cache': True}
        )
        
        # 首先检查 info_data 和 info_data["data"] 的类型
        if info_data and isinstance(info_data, dict):
            # 检查API响应的顶层状态
            if info_data.get("success") and isinstance(info_data.get("data"), dict):
                api_response = info_data["data"]
                # 检查onebot API的status字段
                if api_response.get('status') == 'ok' and api_response.get('retcode') == 0:
                    # 用户数据在api_response['data']中
                    data = api_response.get('data', {})
                    nickname = data.get('nick', '未知')
                    level = data.get('qqLevel', '未知')
                    age = data.get('age', '未知')
                    sex = data.get('sex', '未知')
                    sign = data.get('longNick', '无')
                    
                    # 获取并格式化注册时间
                    reg_time = data.get('regTime', '未知')
                    if reg_time != '未知' and isinstance(reg_time, int):
                        try:
                            register_time = datetime.fromtimestamp(reg_time)
                            register_time = register_time.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            register_time = '格式错误'
                    else:
                        register_time = '未知'
                    
                    # 获取地区信息
                    country = data.get('country', '')
                    province = data.get('province', '')
                    city = data.get('city', '')
                    
                    # 组合地区信息
                    location_parts = [part for part in [country, province, city] if part]
                    location = ' '.join(location_parts) if location_parts else '未知'
                    
                    info_msg = (
                        f"🔍 用户信息查询结果:\n"
                        f"🔹 QQ号: {target_user_id}\n"
                        f"🔹 昵称: {nickname}\n"
                        f"🔹 等级: {level}\n"
                        f"🔹 年龄: {age}\n"
                        f"🔹 性别: {sex}\n"
                        f"🔹 签名: {sign}\n"
                        f"🔹 地区: {location}\n"
                        f"🔹 注册时间: {register_time}"
                    )
                    return info_msg
                else:
                    return f"⚠️ 查询失败: API返回错误 (status: {api_response.get('status')}, retcode: {api_response.get('retcode')})"
            else:
                # 提供更详细的错误信息，包括数据类型
                data_type = type(info_data.get("data")).__name__ if info_data.get("data") is not None else "None"
                return f"⚠️ 查询失败: 返回数据格式不正确 (data类型: {data_type})"
        else:
            return f"⚠️ 查询失败或用户信息不存在"
    except Exception as e:
        logger.error(f"查询用户 {target_user_id} 信息时异常: {e}")
        return f"🛑 查询过程中发生错误: {str(e).split(':')[0]}"  # 只返回错误类型，不返回详细信息