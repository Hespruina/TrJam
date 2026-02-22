# utils.py - 重构后
# 通用工具函数库

from typing import Union, Dict, Any
import os
from PIL import ImageDraw, ImageFont
import aiohttp
import asyncio
from typing import Dict, Any, Union

# 导入统一日志工具
from logger_config import get_logger, log_exception, log_api_request

# 初始化日志记录器
logger = get_logger("Utils")

def calculate_text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """
    计算文本宽度的通用函数
    :param draw: ImageDraw 对象
    :param text: 要计算宽度的文本
    :param font: 使用的字体
    :return: 文本宽度
    """
    try:
        # 推荐方式 (需要 Pillow 8.0.0+)
        return draw.textbbox((0, 0), text, font=font)[2]
    except:
        try:
            # 回退方式 (已弃用的方法)
            return font.getsize(text)[0]
        except:
            # 最后的粗略估算
            return len(text) * 8  # 根据字体大小调整系数

# 注意：safe_api_request 已移至 utils/api_utils.py，此处保留是为了向后兼容
# 强烈建议所有代码使用 utils/api_utils.py 中的版本
async def safe_api_request(url: str, method: str = 'get', params: dict = None, json_data: dict = None, headers: dict = None, timeout: int = 10) -> Union[Dict[str, Any], None]:
    """此函数已废弃，请使用 utils.api_utils.safe_api_request"""
    logger.warning("utils.safe_api_request 已废弃，请使用 utils.api_utils.safe_api_request")
    from utils.api_utils import safe_api_request as new_safe_api_request
    return await new_safe_api_request(url, method, params, json_data, headers, timeout)

# 添加其他通用工具函数
def get_project_root() -> str:
    """
    获取项目根目录
    :return: 项目根目录路径
    """
    return os.path.dirname(os.path.abspath(__file__))

def load_file(file_path: str) -> Union[str, None]:
    """
    安全地读取文件内容
    :param file_path: 文件路径
    :return: 文件内容或None(失败)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        log_exception(logger, f"读取文件失败: {file_path}", e)
        return None

def save_file(file_path: str, content: str) -> bool:
    """
    安全地保存内容到文件
    :param file_path: 文件路径
    :param content: 要保存的内容
    :return: 是否成功
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        log_exception(logger, f"保存文件失败: {file_path}", e)
        return False