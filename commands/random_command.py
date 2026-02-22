# commands/random_command.py
# 处理 /random 命令 - 随机操作功能

import random
from logger_config import get_logger
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from commands.permission_manager import check_permission

logger = get_logger("RandomCommand")

async def handle_random_command(context: BotContext, args: list, user_id: str, group_id: str, command: str, sender_role: str = None, **kwargs) -> str:
    """处理 /random 命令。"""
    
    user_level = check_permission(context, user_id, group_id, sender_role)
    
    if user_level < 1:
        return "❌ 只有管理员才能使用随机命令"
    
    if not args:
        return "❌ 参数错误，格式：/random mute"
    
    subcommand = args[0].lower()
    
    if subcommand == "mute":
        return await _handle_random_mute(context, user_id, group_id)
    else:
        return f"❌ 未知的子命令: {subcommand}，支持的子命令: mute"

async def _handle_random_mute(context: BotContext, user_id: str, group_id: str) -> str:
    """处理随机禁言子命令。"""
    
    bot_qq = str(context.get_config_value("bot_qq", ""))
    root_user = str(context.get_config_value("Root_user", ""))
    
    try:
        response = await call_onebot_api(context, "get_group_member_list", {"group_id": int(group_id)})
        
        if not response or not response.get('success'):
            error_msg = response.get('error', '未知错误') if response else '无响应'
            logger.error(f"获取群成员列表失败，群: {group_id}，原因: {error_msg}")
            return f"🛑 获取群成员列表失败: {error_msg}"
        
        api_data = response.get('data', {})
        logger.info(f"收到群成员列表，群: {group_id}，API响应: {api_data}")
        
        members = api_data.get('data', [])
        logger.info(f"提取成员列表，群: {group_id}，成员数: {len(members) if isinstance(members, list) else 'N/A'}，数据类型: {type(members)}")
        
        if not isinstance(members, list):
            logger.error(f"群成员数据格式错误，群: {group_id}，数据类型: {type(members)}")
            return f"🛑 群成员数据格式错误"
        
        if not members:
            return "❌ 群成员列表为空"
        
        eligible_members = []
        for member in members:
            if not isinstance(member, dict):
                continue
            member_id = str(member.get('user_id', ''))
            member_role = member.get('role', 'member')
            
            if member_id == user_id:
                continue
            if member_id == bot_qq:
                continue
            if member_id == root_user:
                continue
            if member_role in ['owner', 'admin']:
                continue
            
            eligible_members.append(member)
        
        if not eligible_members:
            return "❌ 没有符合条件的群成员（已排除管理员、群主、机器人和Root用户）"
        
        target_member = random.choice(eligible_members)
        target_user_id = str(target_member.get('user_id', ''))
        target_card = target_member.get('card') or target_member.get('nickname', '未知')
        
        mute_duration = 10
        mute_response = await call_onebot_api(
            context, 
            "set_group_ban", 
            {"group_id": int(group_id), "user_id": int(target_user_id), "duration": mute_duration}
        )
        
        if mute_response and mute_response.get('success') and mute_response.get('data', {}).get('status') == 'ok':
            logger.info(f"已成功随机禁言用户 {target_user_id} ({target_card})，群: {group_id}，时长: {mute_duration}秒")
            return f"🎲 随机禁言选中了 {target_card} ({target_user_id})，禁言 {mute_duration} 秒"
        else:
            failure_reason = "未知原因"
            if mute_response:
                if not mute_response.get('success'):
                    failure_reason = mute_response.get('error', 'API调用失败')
                else:
                    failure_reason = f"业务状态非成功: {mute_response.get('data', {}).get('status', '未知')}"
            logger.error(f"随机禁言失败，群: {group_id}，用户: {target_user_id}，原因: {failure_reason}")
            return f"🛑 禁言失败: {failure_reason}"
            
    except Exception as e:
        logger.error(f"处理随机禁言时发生异常: {e}")
        return f"🛑 执行随机禁言时发生错误: {e}"
