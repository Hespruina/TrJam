# handlers/notice_handler.py
# 处理通知事件

import asyncio
import time
import os
import json
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.user_utils import get_user_nickname
from utils.message_sender import MessageBuilder

logger = get_logger("NoticeHandler")



# 存储用户戳机器人记录 {group_id: {user_id: [timestamp, ...]}}
poke_records = {}
# 存储用户冷却时间 {group_id: {user_id: cooldown_end_time}}
poke_cooldowns = {}


async def handle_notice_event(context: BotContext, event: dict):
    """处理通知事件。"""
    # 检查是否应该处理该消息（基于当前活跃账号）
    if not context.should_handle_message(event):
        return
        
    notice_type = event.get('notice_type')
    
    if notice_type == 'friend_add':
        await _handle_friend_add(context, event)
    elif notice_type == 'group_decrease':
        await _handle_group_decrease(context, event)
    elif notice_type == 'group_upload':
        await _handle_group_upload(context, event)
    elif notice_type == 'poke':
        await _handle_poke_event(context, event)
    elif notice_type == 'group_increase':
        await _handle_group_increase(context, event)

async def _handle_friend_add(context: BotContext, event: dict):
    """处理好友添加事件。"""
    user_id = event.get('user_id', '')
    logger.info(f"用户 {user_id} 已添加机器人为好友")
    
    # 可以在这里添加其他处理逻辑，例如：
    # 1. 发送欢迎消息
    # 2. 记录到数据库
    # 3. 推送通知给管理员等


async def _handle_group_decrease(context: BotContext, event: dict):
    """处理群成员减少事件。"""
    group_id = event.get('group_id', '')
    user_id = event.get('user_id', '')
    operator_id = event.get('operator_id', '')
    sub_type = event.get('sub_type', '')

    # 检查是否启用了退群推送功能
    group_config_path = f"data/group_config/{group_id}.json"
    group_toggle_config = {}
    if os.path.exists(group_config_path):
        try:
            with open(group_config_path, 'r', encoding='utf-8') as f:
                group_toggle_config = json.load(f)
        except Exception as e:
            logger.error(f"读取群组配置文件失败: {e}")

    # 检查是否启用了 group_exit 功能
    group_exit_enabled = group_toggle_config.get("group_exit_enabled", False)
    if not group_exit_enabled:
        logger.debug(f"群 {group_id} 未启用退群推送功能，跳过处理")
        return

    # 获取群组配置
    group_config = context.get_group_config(str(group_id))
    api_base = group_config.get("api_base", "") if group_config else ""

    user_nickname = await get_user_nickname(context, user_id)
    if sub_type == 'leave':
        notice_msg = f"{user_nickname}（{user_id}）退出群聊。"
        logger.info(f"用户 {user_id}({user_nickname}) 主动退出群 {group_id}")
    elif sub_type == 'kick':
        operator_nickname = await get_user_nickname(context, operator_id)
        notice_msg = f"{operator_nickname}（{operator_id}）将{user_nickname}（{user_id}）移出了群聊。"
        logger.info(f"用户 {user_id}({user_nickname}) 被 {operator_id}({operator_nickname}) 踢出群 {group_id}")
    else:
        notice_msg = f"{user_nickname}（{user_id}）离开群聊，类型: {sub_type}。"
        logger.info(f"用户 {user_id}({user_nickname}) 离开群 {group_id}，类型: {sub_type}")

    # 发送通知到群
    builder = MessageBuilder(context)
    builder.set_group_id(group_id)
    builder.add_text(notice_msg)
    await builder.send()





async def _handle_group_upload(context: BotContext, event: dict):
    """处理群文件上传事件。"""
    group_id = event.get('group_id', '')
    user_id = event.get('user_id', '')
    file_info = event.get('file', {})
    
    file_name = file_info.get('name', '未知文件')
    file_size = file_info.get('size', 0)
    file_id = file_info.get('id', '')
    
    logger.info(f"群 {group_id} 中用户 {user_id} 上传了文件: {file_name}")
    
    # 获取用户昵称
    user_nickname = await get_user_nickname(context, user_id)
    
    # 记录文件上传日志，但不发送消息到群聊
    file_size_mb = file_size / (1024 * 1024)  # 转换为MB
    logger.info(f"{user_nickname} 上传了文件: {file_name} ({file_size_mb:.2f}MB)")
    
    # 注释掉发送提示到群的代码
    # builder = MessageBuilder(context)
    # builder.set_group_id(group_id)
    # builder.add_text(upload_tip)
    # await builder.send()


async def _handle_poke_event(context: BotContext, event: dict):
    """处理戳一戳事件。"""
    group_id = event.get('group_id')
    user_id = event.get('user_id', '')
    target_id = event.get('target_id', '')
    
    bot_qq = str(context.get_config_value('bot_qq', ''))
    
    # 只处理戳机器人的事件
    if target_id != bot_qq:
        return
    
    # 检查用户是否在冷却期
    current_time = time.time()
    if group_id in poke_cooldowns and user_id in poke_cooldowns[group_id]:
        if current_time < poke_cooldowns[group_id][user_id]:
            # 用户仍在冷却期，忽略戳一戳事件
            return
        else:
            # 冷却期已过，移除冷却记录
            del poke_cooldowns[group_id][user_id]
    
    logger.info(f"用户 {user_id} 在群 {group_id} 戳了机器人")
    
    # 初始化记录结构
    if group_id not in poke_records:
        poke_records[group_id] = {}
    
    if user_id not in poke_records[group_id]:
        poke_records[group_id][user_id] = []
    
    # 清理一分钟前的记录
    poke_records[group_id][user_id] = [
        timestamp for timestamp in poke_records[group_id][user_id]
        if current_time - timestamp <= 60
    ]
    
    # 添加当前戳机器人事件
    poke_records[group_id][user_id].append(current_time)
    
    # 计算用户在一分钟内的戳机器人次数
    poke_count = len(poke_records[group_id][user_id])
    
    # 获取用户昵称
    user_nickname = await get_user_nickname(context, user_id)
    
    # 最多只戳回去3次
    if poke_count <= 3:
        # 发送回应消息
        builder = MessageBuilder(context)
        builder.set_group_id(str(group_id))
        if poke_count == 1:
            builder.add_text(f"喂！{user_nickname}！你戳我干嘛？")
        else:
            builder.add_text(f"喂！{user_nickname}！你已经戳了我 {poke_count} 次了！")
        await builder.send()
        
        # 回戳用户
        poke_api_data = {
            "group_id": group_id,
            "user_id": user_id
        }
        await call_onebot_api(context, "send_group_poke", poke_api_data)
        
        # 如果达到3次，设置30秒冷却期
        if poke_count == 3:
            if group_id not in poke_cooldowns:
                poke_cooldowns[group_id] = {}
            poke_cooldowns[group_id][user_id] = current_time + 30
    elif poke_count == 4:
        # 第四次提醒用户
        builder = MessageBuilder(context)
        builder.set_group_id(str(group_id))
        builder.add_text(f"{user_nickname}，你已经戳了我好多次了，我最多只会回戳3次哦~")
        await builder.send()
        
        # 设置30秒冷却期
        if group_id not in poke_cooldowns:
            poke_cooldowns[group_id] = {}
        poke_cooldowns[group_id][user_id] = current_time + 30

async def _handle_group_increase(context: BotContext, event: dict):
    """处理群成员增加事件。"""
    group_id = event.get('group_id', '')
    user_id = event.get('user_id', '')
    self_id = event.get('self_id', '')
    
    # 获取机器人QQ号
    bot_qq = str(context.get_config_value('bot_qq', ''))
    
    # 检查新加入的成员是否是机器人自己
    if str(user_id) == bot_qq:
        logger.info(f"机器人 {bot_qq} 被加入群 {group_id}")
        
        # 从配置中获取提示消息内容，默认为"大家好，我是机器人！"
        join_message = context.get_config_value('join_group_message', '大家好，我是机器人！')
        
        # 发送提示消息到群聊
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(join_message)
        await builder.send()
        logger.info(f"已向群 {group_id} 发送入群提示消息")
        
        # 向report群发送机器人入群通知
        report_group_id = context.get_config_value("report_group")
        if report_group_id:
            from utils.user_utils import get_user_nickname
            import time
            timestamp = int(time.time())
            formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            
            # 构建报告消息
            report_message = [
                {"type": "text", "data": {"text": "【机器人入群通知】"}},
                {"type": "text", "data": {"text": f"\n时间: {formatted_time}"}},
                {"type": "text", "data": {"text": f"\n机器人QQ: {bot_qq}"}},
                {"type": "text", "data": {"text": f"\n群号: {group_id}"}}
            ]
            
            # 发送报告消息到report群
            builder = MessageBuilder(context)
            builder.set_group_id(str(report_group_id))
            builder.set_badword_bypass(True, "管理员敏感词报告", "system")
            for text in report_message:
                builder.add_text(text['data']['text'])
            await builder.send()
            logger.info(f"已向report群 {report_group_id} 发送机器人入群通知")


