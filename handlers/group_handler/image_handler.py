# handlers/group_handler/image_handler.py
# 处理图片消息和腿照识别

import json
import uuid
import os
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder
from utils.task_utils import create_monitored_task
# 导入图片处理相关函数
from utils.vision_utils import download_image_async, image_to_base64_async, is_leg_photo_async
from utils.api_utils import call_onebot_api

logger = get_logger("ImageHandler")

async def handle_image_messages(context: BotContext, event: dict, group_id: str, user_id: str, nickname: str):
    """处理消息中的图片，识别腿照并设置精华"""
    # 检查是否启用了腿照自动设为精华功能
    # 使用toggle功能控制的配置
    group_config = context.get_group_config(str(group_id))
    leg_photo_enabled = group_config.get("leg_photo_essence_enabled", False) if group_config else False
    if not leg_photo_enabled:
        logger.debug(f"腿照自动设为精华功能未启用，群: {group_id}")
        return

    # 检查全局LLM开关
    if not context.get_config_value("llm_enabled", False):
        logger.debug("LLM功能已禁用，跳过腿照识别")
        return

    # 从消息中提取图片URL
    message = event.get('message', [])
    image_urls = extract_image_urls(message)
    
    # 如果没有图片，直接返回
    if not image_urls:
        return

    # 从配置获取最多处理的图片数量
    ai_vision_config = context.get_config_value("ai_vision", {})
    if ai_vision_config:
        leg_detection_config = ai_vision_config.get("leg_photo_detection", {})
        max_images = leg_detection_config.get("max_images_per_message", 3)
    else:
        max_images = 3
    
    # 限制处理的图片数量，避免API调用过多
    image_urls = image_urls[:max_images]

    logger.debug(f"检测到群 {group_id} 中用户 {user_id}({nickname}) 发送了 {len(image_urls)} 张图片，准备进行腿照识别")
    
    # 创建后台任务处理图片，避免阻塞WebSocket连接
    create_monitored_task(
        process_image_for_leg_detection(context, event, group_id, user_id, nickname, image_urls),
        f"LegPhotoDetection-{group_id}-{user_id}"
    )

def extract_image_urls(message):
    """从消息中提取图片URL"""
    image_urls = []
    if isinstance(message, list):
        for segment in message:
            if isinstance(segment, dict) and segment.get('type') == 'image':
                # 尝试获取URL，OneBot不同版本字段可能不同
                image_url = segment.get('data', {}).get('url')
                if not image_url:
                    image_url = segment.get('data', {}).get('file')
                if image_url:
                    image_urls.append(image_url)
    return image_urls

async def process_image_for_leg_detection(context, event, group_id, user_id, nickname, image_urls):
    """在后台处理图片并识别腿照的协程函数"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    temp_dir = os.path.join(project_root, 'temp_images')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        
    try:
        for image_url in image_urls:
            save_path = os.path.join(temp_dir, f"temp_image_{uuid.uuid4()}.jpg")
            try:
                await download_image_async(image_url, save_path)
                # 转换为base64
                base64_image = await image_to_base64_async(save_path)
                
                # 识别是否为腿照
                if base64_image:
                    is_leg_photo = await is_leg_photo_async(context, base64_image)
                    if is_leg_photo and event.get('message_id'):
                        # 调用onebot API设置精华消息
                        essence_result = await call_onebot_api(
                            context, 'set_essence_msg', {'message_id': event.get('message_id')}
                        )
                        # 检查设置精华是否成功
                        if essence_result and essence_result.get('success') and essence_result.get('data', {}).get('status') == 'ok':
                            logger.info(f"成功将腿照设置为精华消息，群: {group_id}，用户: {user_id}({nickname})")
                            # 发送提示消息
                            builder = MessageBuilder(context)
                            builder.set_group_id(str(group_id))
                            builder.set_user_id(user_id)
                            builder.add_at()
                            builder.add_text(" 腿照已被设为精华！")
                            await builder.send()
                            break  # 找到一张腿照并设为精华后就可以退出了
                        else:
                            logger.error(f"设置精华消息失败，群: {group_id}，用户: {user_id}")
            except Exception as e:
                log_exception(logger, f"处理图片 {image_url} 时发生异常", e)
            finally:
                # 清理临时文件
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except Exception as e:
                        logger.error(f"删除临时文件失败: {save_path}", e)
    except Exception as e:
        log_exception(logger, "处理图片消息时发生异常", e)