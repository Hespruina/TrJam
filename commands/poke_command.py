# 处理 '/poke' 命令

from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_utils import parse_at_or_qq
from utils.api_utils import call_onebot_api
from utils.message_sender import MessageBuilder, CommandResponse
from utils.task_utils import create_monitored_task
from .permission_manager import check_permission
import asyncio
import time

logger = get_logger("PokeCommand")

# 存储用户最后一次执行poke命令的时间戳
# {user_id: last_execution_time}
poke_cooldowns = {}

async def handle_poke_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """处理 '/poke' 命令，戳指定QQ号用户。"""
    try:
        # 解析参数中的QQ号或@
        target_qq, remaining_args = parse_at_or_qq(args)
        if not target_qq:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("❌ 请指定要戳的用户QQ号或@对方")
            await builder.send()
            return CommandResponse.none()
        
        # 获取机器人自身的QQ号
        bot_qq = str(context.get_config_value('bot_qq', ''))
        # 检查是否戳的是机器人自己
        if str(target_qq) == bot_qq:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("❌ 不能戳我哦~ 会坏掉的！")
            await builder.send()
            return CommandResponse.none()
        
        # 检查权限级别
        user_level = check_permission(context, user_id, group_id)
        
        # 检查冷却时间（20秒）
        current_time = time.time()
        if user_level < 2:  # 只有Root用户没有冷却时间
            last_time = poke_cooldowns.get(user_id, 0)
            cooldown_time = 20  # 20秒冷却时间
            if current_time - last_time < cooldown_time:
                remaining_time = int(cooldown_time - (current_time - last_time))
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text(f"⏱️ 戳戳功能冷却中，请等待 {remaining_time} 秒后再试~")
                await builder.send()
                return CommandResponse.none()
        
        # 解析戳戳次数
        times = 1  # 默认戳1次
        if remaining_args and remaining_args[0].isdigit():
            times = int(remaining_args[0])
            # 检查次数限制
            if user_level < 2:  # 非Root用户限制5次
                if times > 5:
                    builder = MessageBuilder(context)
                    builder.set_group_id(group_id)
                    builder.set_user_id(user_id)
                    builder.add_at()
                    builder.add_text("⚠️ 最多只能戳5下哦~")
                    await builder.send()
                    return CommandResponse.none()
            elif times <= 0:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❌ 戳戳次数必须大于0！")
                await builder.send()
                return CommandResponse.none()
        
        logger.info(f"用户 {user_id} 在群 {group_id} 执行了 poke 命令，目标QQ: {target_qq}，次数: {times}")
        
        # 更新冷却时间（非Root用户）
        if user_level < 2:
            poke_cooldowns[user_id] = time.time()
        
        # 创建后台任务处理耗时的戳戳操作
        create_monitored_task(
            process_poke_request(context, user_id, group_id, target_qq, times),
            name=f"PokeCommand_process_{user_id}_{group_id}_{target_qq}"
        )
        
        # 返回none表示已经通过builder发送了消息
        return CommandResponse.none()
        
    except Exception as e:
        logger.error(f"处理poke命令时发生异常: {e}", exc_info=True)
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("❌ 戳戳失败，请稍后再试~")
        await builder.send()
        return CommandResponse.none()

async def process_poke_request(context: BotContext, user_id: str, group_id: str, target_qq: str, times: int):
    """在后台处理戳戳请求的耗时操作"""
    try:
        # 使用call_onebot_api发送戳戳消息
        success_count = 0
        for i in range(times):
            try:
                # 调用group_poke API
                response = await call_onebot_api(
                    context=context,
                    action="group_poke",
                    params={
                        "group_id": group_id,
                        "user_id": target_qq
                    }
                )
                
                # 检查API调用结果
                if response and response.get('success'):
                    response_data = response.get('data', {})
                    if response_data.get('status') == 'ok':
                        success_count += 1
                        logger.info(f"已在群 {group_id} 第 {i+1}/{times} 次戳用户 {target_qq}")
                    else:
                        logger.warning(f"在群 {group_id} 第 {i+1}/{times} 次戳用户 {target_qq} 失败: {response_data}")
                else:
                    logger.error(f"调用group_poke API失败: {response.get('error') if response else '无响应'}")
                
                # 在每次戳之间添加小延迟
                if i < times - 1:  # 不是最后一次戳
                    await asyncio.sleep(0.3)
                    
            except Exception as api_error:
                logger.error(f"调用group_poke API失败: {api_error}")
        
        # 发送结果消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        
        if success_count > 0:
            builder.add_text(f"✅ 已成功戳了 {target_qq} {success_count}次~")
        else:
            builder.add_text("❌ 戳戳失败，请稍后再试~")
        
        await builder.send()
        
    except Exception as e:
        logger.error(f"处理戳戳请求时发生异常: {e}", exc_info=True)
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("❌ 戳戳过程中发生错误，请稍后再试~")
        await builder.send()