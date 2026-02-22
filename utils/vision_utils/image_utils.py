# utils/vision_utils/image_utils.py
# 图片处理工具函数

import base64
import os
import aiohttp
from typing import Optional
from logger_config import get_logger, log_exception

logger = get_logger("VisionUtilsImage")

async def image_to_base64_async(image_path: str) -> Optional[str]:
    """异步读取图片并转换为 base64 字符串"""
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片路径不存在: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        log_exception(logger, f"读取图片失败: {image_path}", e)
        return None

def get_image_mime_type(image_path: str) -> str:
    """简单根据文件扩展名判断 MIME 类型"""
    ext = os.path.splitext(image_path)[1].lower()
    if ext in ['.jpg', '.jpeg']:
        return 'image/jpeg'
    elif ext in ['.png']:
        return 'image/png'
    elif ext in ['.gif']:
        return 'image/gif'
    elif ext in ['.webp']:
        return 'image/webp'
    else:
        return 'image/jpeg'  # 默认

async def download_image_async(url: str, save_path: str) -> bool:
    """异步下载图片"""
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                with open(save_path, 'wb') as f:
                    f.write(await response.read())
                return True
    except Exception as e:
        log_exception(logger, f"下载图片失败: {url}", e)
        return False