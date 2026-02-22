# muteme命令模块

from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import CommandResponse, MessageBuilder
from utils.api_utils import call_onebot_api
from utils.task_utils import create_monitored_task
import asyncio

logger = get_logger("MutemeCommand")

async def handle_muteme_command(context: BotContext, **kwargs) -> CommandResponse:
    """处理muteme命令：主动请求禁言并在10秒后自动解除"""
    user_id = kwargs.get('user_id')
    group_id = kwargs.get('group_id')
    nickname = kwargs.get('nickname', '未知用户')
    
    logger.info(f"用户 {user_id}({nickname}) 请求主动禁言")
    
    try:
        # 禁言时长（11天4小时5分钟）
        mute_duration = 950400 + 14400 + 300
        
        # 执行禁言操作
        mute_result = await call_onebot_api(
            context, 'set_group_ban',
            {
                'group_id': group_id,
                'user_id': user_id,
                'duration': mute_duration
            }
        )
        
        # 检查API调用是否成功
        if mute_result and mute_result.get('success') and mute_result.get('data', {}).get('status') == 'ok':
            logger.info(f"成功禁言用户 {user_id}({nickname})，时长：{mute_duration}秒")
            
            # 构建消息并发送
            builder = MessageBuilder(context)
            builder.set_group_id(str(group_id))
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(" 已为您禁言11天4小时5分钟捏")
            await builder.send()

            # 创建一个后台任务，在10秒后自动解禁
            async def auto_unmute_task():
                await asyncio.sleep(10)
                try:
                    unmute_result = await call_onebot_api(
                        context, 'set_group_ban',
                        {
                            'group_id': group_id,
                            'user_id': user_id,
                            'duration': 0
                        }
                    )
                    # 检查API调用是否成功
                    if unmute_result and unmute_result.get('success') and unmute_result.get('data', {}).get('status') == 'ok':
                        logger.info(f"成功取消用户 {user_id}({nickname}) 的禁言")
                        
                        # 发送解禁通知
                        builder = MessageBuilder(context)
                        builder.set_group_id(str(group_id))
                        builder.set_user_id(user_id)
                        builder.add_at()
                        builder.add_text(" 您的禁言已自动解除")
                        await builder.send()
                    else:
                        logger.error(f"取消用户 {user_id}({nickname}) 禁言失败")
                except Exception as e:
                    logger.error(f"自动解禁用户时发生异常: {e}")

            # 使用create_monitored_task创建后台任务
            create_monitored_task(auto_unmute_task(), name=f"AutoUnmute_{user_id}_{group_id}")
            
            # 返回空响应，因为我们已经直接发送了消息
            return CommandResponse.none()
        else:
            # 提供更详细的失败原因
            failure_reason = "未知原因"
            if mute_result:
                if not mute_result.get('success'):
                    failure_reason = mute_result.get('error', 'API调用失败')
                else:
                    failure_reason = f"业务状态非成功: {mute_result.get('data', {}).get('status', '未知')}"
            logger.error(f"禁言用户失败，群: {group_id}，用户: {user_id}，原因: {failure_reason}")
            
            # 返回失败消息
            return CommandResponse.text(f"禁言失败：{failure_reason}")
            
    except Exception as e:
        logger.error(f"处理用户主动禁言时发生异常: {e}")
        # 返回异常消息
        return CommandResponse.text("禁言处理过程中发生异常，请联系管理员")