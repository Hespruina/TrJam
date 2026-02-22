# handlers/group_handler/auto_mute_handler.py
# 处理自动禁言

import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder
from utils.api_utils import call_onebot_api
from utils.task_utils import create_monitored_task

logger = get_logger("AutoMuteHandler")

async def handle_auto_mute(context: BotContext, user_id: str, nickname: str, group_id: str):
    """处理用户主动请求禁言。"""
    logger.info(f"用户 {user_id}({nickname}) 请求主动禁言")
    try:
        mute_duration = 950400 + 14400 + 300 # 11天4小时5分钟
        mute_result = await call_onebot_api(
            context, 'set_group_ban',
            {
                'group_id': group_id,
                'user_id': user_id,
                'duration': mute_duration
            }
        )
        # 检查API调用是否成功以及业务处理是否成功
        if mute_result and mute_result.get('success') and mute_result.get('data', {}).get('status') == 'ok':
            logger.info(f"成功禁言用户 {user_id}({nickname})，时长：{mute_duration}秒")
            # 构建消息并发送
            builder = MessageBuilder(context)
            builder.set_group_id(str(group_id))
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(" 已为您禁言11天4小时5分钟捏")
            await builder.send()

            # 创建一个后台任务，在20秒后自动解禁
            async def auto_unmute_task():
                await asyncio.sleep(20)
                try:
                    unmute_result = await call_onebot_api(
                        context, 'set_group_ban',
                        {
                            'group_id': group_id,
                            'user_id': user_id,
                            'duration': 0
                        }
                    )
                    # 检查API调用是否成功以及业务处理是否成功
                    if unmute_result and unmute_result.get('success') and unmute_result.get('data', {}).get('status') == 'ok':
                        logger.info(f"成功取消用户 {user_id}({nickname}) 的禁言")
                    else:
                        logger.error(f"取消用户 {user_id}({nickname}) 禁言失败")
                except Exception as e:
                    logger.error(f"自动解禁用户时发生异常: {e}")

            # 使用create_monitored_task创建后台任务
            create_monitored_task(auto_unmute_task(), name=f"AutoUnmute_{user_id}_{group_id}")
        else:
            # 提供更详细的失败原因
            failure_reason = "未知原因"
            if mute_result:
                if not mute_result.get('success'):
                    failure_reason = mute_result.get('error', 'API调用失败')
                else:
                    failure_reason = f"业务状态非成功: {mute_result.get('data', {}).get('status', '未知')}"
            logger.error(f"禁言用户失败，群: {group_id}，用户: {user_id}，原因: {failure_reason}")
            # 发送失败消息
            builder = MessageBuilder(context)
            builder.set_group_id(str(group_id))
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f" 禁言失败：{failure_reason}")
            await builder.send()
    except Exception as e:
        logger.error(f"处理用户主动禁言时发生异常: {e}")
        # 发送异常消息
        builder = MessageBuilder(context)
        builder.set_group_id(str(group_id))
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" 禁言处理过程中发生异常，请联系管理员")
        await builder.send()