# commands/bapic_command.py
# 蔚蓝档案图片命令处理器

import asyncio
import os
import json
import random
import datetime
import aiohttp
import hashlib
from typing import Optional
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from utils.task_utils import create_monitored_task

logger = get_logger("BapicCommand")

# 图片API设置
PORTRAIT_API = "https://rba.kanostar.top/portrait"
LANDSCAPE_API = "https://rba.kanostar.top/landscape"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_CACHE_DIR = os.path.join(SCRIPT_DIR, "..", "assets", "image", "YunShi")
LIMIT_FILE_PATH = os.path.join(SCRIPT_DIR, "..", "data", "jrys_bluearchive_limit.json")

# 速率限制配置
RATE_LIMITS = {
    "second": 3,  # 每秒限制
    "minute": 150,  # 每分钟限制
    "hour": 1500,  # 每小时限制
    "day": 4500  # 每天限制
}

# 确保目录存在
def ensure_directories():
    os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LIMIT_FILE_PATH), exist_ok=True)

# 加载速率限制数据
def load_rate_limit_data():
    ensure_directories()
    if os.path.exists(LIMIT_FILE_PATH):
        try:
            with open(LIMIT_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 确保数据格式正确
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.error(f"加载速率限制数据失败: {e}")
    return []

# 保存速率限制数据
def save_rate_limit_data(data):
    try:
        with open(LIMIT_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存速率限制数据失败: {e}")

# 检查是否达到速率限制
def check_rate_limits():
    current_time = datetime.datetime.now()
    timestamps = load_rate_limit_data()
    
    # 过滤出有效的时间戳（保留最近24小时的）
    valid_timestamps = []
    for ts in timestamps:
        try:
            timestamp = datetime.datetime.fromisoformat(ts)
            # 只保留最近24小时的记录
            if (current_time - timestamp).total_seconds() < 86400:
                valid_timestamps.append(ts)
        except Exception as e:
            logger.error(f"解析时间戳失败: {e}")
    
    # 保存过滤后的数据
    save_rate_limit_data(valid_timestamps)
    
    # 检查各时间维度的限制
    for ts in valid_timestamps:
        timestamp = datetime.datetime.fromisoformat(ts)
        time_diff = (current_time - timestamp).total_seconds()
        
        # 检查每秒限制
        if time_diff < 1:
            if valid_timestamps.count(ts) >= RATE_LIMITS["second"]:
                return True
        
    # 检查每分钟限制
    minute_count = 0
    for ts in valid_timestamps:
        timestamp = datetime.datetime.fromisoformat(ts)
        if (current_time - timestamp).total_seconds() < 60:
            minute_count += 1
    if minute_count >= RATE_LIMITS["minute"]:
        return True
    
    # 检查每小时限制
    hour_count = 0
    for ts in valid_timestamps:
        timestamp = datetime.datetime.fromisoformat(ts)
        if (current_time - timestamp).total_seconds() < 3600:
            hour_count += 1
    if hour_count >= RATE_LIMITS["hour"]:
        return True
    
    # 检查每天限制
    day_count = len(valid_timestamps)
    if day_count >= RATE_LIMITS["day"]:
        return True
    
    return False

# 记录API调用
def record_api_call():
    current_time = datetime.datetime.now().isoformat()
    timestamps = load_rate_limit_data()
    timestamps.append(current_time)
    save_rate_limit_data(timestamps)

# 从API获取图片并保存
async def fetch_image_from_api(api_url):
    try:
        # 检查速率限制
        if check_rate_limits():
            logger.info("已达到API调用速率限制，使用缓存图片")
            return None
        
        # 确保目录存在
        ensure_directories()
        
        # 从API获取图片
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=HEADERS, timeout=10) as response:
                if response.status != 200:
                    logger.error(f"获取图片失败，状态码: {response.status}")
                    return None
                
                # 读取图片数据
                image_data = await response.read()
        
        # 生成唯一文件名
        md5_hash = hashlib.md5(image_data).hexdigest()
        file_extension = "png"  # 假设API返回PNG格式
        filename = f"{md5_hash}.{file_extension}"
        file_path = os.path.join(IMAGE_CACHE_DIR, filename)
        
        # 保存图片
        with open(file_path, "wb") as f:
            f.write(image_data)
        
        # 记录API调用
        record_api_call()
        
        logger.info(f"成功从API获取并保存图片: {filename}")
        return file_path
    except Exception as e:
        logger.error(f"获取图片时发生错误: {e}")
        return None

# 从缓存获取随机图片
def get_random_cached_image():
    ensure_directories()
    try:
        files = [f for f in os.listdir(IMAGE_CACHE_DIR) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
        if not files:
            return None
        return os.path.join(IMAGE_CACHE_DIR, random.choice(files))
    except Exception as e:
        logger.error(f"获取缓存图片失败: {e}")
        return None

# 获取蔚蓝档案图片（1/3概率使用原API，1/3概率使用新API，1/3概率使用缓存）
async def get_bluearchive_image():
    # 随机选择图片来源
    choice = random.random()
    
    if choice < 1/3:
        # 1/3概率使用原API
        image_path = await fetch_image_from_api(PORTRAIT_API)
        # 如果API获取失败，尝试使用缓存
        if not image_path:
            image_path = get_random_cached_image()
        return image_path
    elif choice < 2/3:
        # 1/3概率使用新API
        image_path = await fetch_image_from_api(LANDSCAPE_API)
        # 如果API获取失败，尝试使用缓存
        if not image_path:
            image_path = get_random_cached_image()
        return image_path
    else:
        # 1/3概率使用缓存图片
        image_path = get_random_cached_image()
        # 如果缓存中没有图片，尝试从任一API获取
        if not image_path:
            # 随机选择一个API
            api_choice = random.choice([PORTRAIT_API, LANDSCAPE_API])
            image_path = await fetch_image_from_api(api_choice)
        return image_path

async def handle_bapic_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """
    处理 /bapic 命令，随机发送一张蔚蓝档案图片
    
    :param context: 机器人上下文，包含配置和WebSocket
    :param args: 命令参数列表（已去除命令名）
    :param user_id: 触发命令的用户QQ号
    :param group_id: 触发命令的群号
    :param server_name: 当前服务器名称
    :param kwargs: 其他可能的参数（如nickname、api_base、cmd_config、user_level等）
    :return: CommandResponse对象，包含要发送的响应
    """
    logger.info(f"用户 {user_id} 在群 {group_id} 执行了 /bapic 命令")
    
    # 发送处理中提示并保存消息ID
    processing_builder = MessageBuilder(context)
    processing_builder.set_group_id(group_id)
    processing_builder.set_user_id(user_id)
    processing_builder.add_at()
    processing_builder.add_text("获取中...")
    
    async def processing_callback(message_id: str):
        if message_id:
            # 启动后台任务处理图片获取，并传递处理中消息的ID
            create_monitored_task(
                process_bapic_request(context, args, user_id, group_id, message_id, **kwargs),
                name=f"BapicCommand_process_{user_id}_{group_id}"
            )
    
    processing_builder.set_callback(processing_callback)
    
    # 先发送处理中提示
    await processing_builder.send()
    
    # 返回None表示已经通过builder发送了消息
    return CommandResponse.none()

async def process_bapic_request(context: BotContext, args: list, user_id: str, group_id: str, processing_message_id: str, **kwargs) -> None:
    """在后台处理蔚蓝档案图片请求"""
    # 获取用户昵称
    nickname = kwargs.get('nickname', f"用户{user_id[-4:]}")
    
    try:
        # 获取蔚蓝档案图片
        image_path = await get_bluearchive_image()
        
        # 构建消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(f"来咯~\n")
        
        # 添加图片
        if image_path:
            builder.add_image(image_path)
        else:
            builder.add_text("❌ 无法获取图片，请稍后再试")
        
        # 发送最终结果
        await builder.send()
        
        # 尝试撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)
        
    except Exception as e:
        logger.error(f"获取蔚蓝档案图片失败: {e}")
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"❌ 获取图片失败：{str(e)}")
        await error_builder.send()
        
        # 尝试撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)

async def try_recall_processing_message(context: BotContext, processing_message_id: str) -> None:
    """尝试撤回处理中提示消息"""
    try:
        # 等待一段时间确保消息发送完成
        await asyncio.sleep(1)
        
        # 调用API撤回消息
        from utils.api_utils import call_onebot_api
        result = await call_onebot_api(
            context=context,
            action="delete_msg",
            params={"message_id": processing_message_id}
        )
        
        if not (result and result.get("success")):
            logger.warning(f"撤回处理中提示消息失败: {result}")
    except Exception as e:
        logger.warning(f"撤回处理中提示消息时发生异常: {e}")
