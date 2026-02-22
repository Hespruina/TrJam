# commands/like_command.py
# 处理 '赞我' 命令

from logger_config import get_logger
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.task_utils import create_monitored_task
from utils.message_sender import MessageBuilder, CommandResponse
import asyncio

logger = get_logger("LikeCommand")

async def handle_like_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """处理 '赞我' 命令，为用户发送多次名片赞，直到无法继续点赞为止"""
    
    # 创建后台任务处理耗时的点赞操作
    create_monitored_task(
        process_like_request(context, user_id, group_id),
        name=f"LikeCommand_process_{user_id}_{group_id}"
    )
    
    # 不发送"正在处理"提示，直接返回空响应
    return CommandResponse.none()

async def process_like_request(context: BotContext, user_id: str, group_id: str):
    """
    在后台处理点赞请求的操作
    
    :param context: 机器人上下文
    :param user_id: 用户ID
    :param group_id: 群ID
    """
    try:
        # 持续点赋试验，直到失败为止
        success_count = 0
        max_attempts = 60  # 最大尝试次数保持60次以检测假成功情况
        
        logger.info(f"开始为用户 {user_id} 执行名片赞操作")
        
        for i in range(max_attempts):
            # 构建请求参数，每次点10个赞
            payload = {
                "user_id": user_id,
                "times": 10  # 每次点10个赞
            }
            
            # 调用onebot API发送点赞请求
            result = await call_onebot_api(
                context=context,
                action="send_like",
                params=payload
            )
            
            # 检查API返回结果
            if not result:
                logger.error(f"名片赞API调用失败，无返回结果")
                break
            
            # 根据data中的status字段判断是否成功
            if result.get("data") and result["data"].get("status") == "ok":
                success_count += 1
                logger.info(f"为用户 {user_id} 第 {success_count} 次名片赞操作成功（每次10个）")
                
                # 如果还没达到最大尝试次数，短暂延迟后继续下一次
                if i < max_attempts - 1:
                    await asyncio.sleep(1)  # 短暂延迟1秒
            else:
                logger.info(f"为用户 {user_id} 名片赞操作失败，停止点赞。返回结果: {result}")
                break
        
        # 发送最终结果给用户，将成功次数乘以10
        if success_count >= 60:
            # 如果成功次数达到60次，说明是假成功情况，提示用户加好友重试
            message = "❌ 请先添加机器人为好友再重试"
        elif success_count > 0:
            total_likes = success_count * 10  # 每次点10个赞，所以总数要乘以10
            message = f"已完成{total_likes}个名片赞，记得回哦~\n如果没收到请加好友重试\n感谢 酒娘虐你风情 赠送的SVIP"
        else:
            message = "点赞失败喵，是不是赞过了喵？"
        
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"\n{message}")
        builder.set_auto_recall(20)  # 设置20秒后自动撤回
        
        # 发送最终结果
        await builder.send()
        
    except Exception as e:
        logger.error(f"执行名片赞操作时发生异常: {e}")
        # 发送错误消息
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"\n❌ 点赞过程中发生错误: {str(e)}")
        
        await error_builder.send()