# utils/vision_utils/leg_photo_detector.py
# 腿部照片检测器

from logger_config import get_logger
from core.bot_context import BotContext
from utils.vision_utils.siliconflow_api import call_siliconflow_api_async

logger = get_logger("LegPhotoDetector")

async def is_leg_photo_async(context: BotContext, base64_image: str) -> bool:
    """判断是否为腿部实拍照片（包含多次识别确认机制）"""
    # 检查全局LLM开关
    if not context.get_config_value("llm_enabled", False):
        logger.debug("LLM功能已禁用，跳过腿照识别")
        return False
        
    # 检查功能是否启用
    ai_vision_config = context.get_config_value("ai_vision", {})
    leg_detection_config = ai_vision_config.get("leg_photo_detection", {}) if ai_vision_config else {}
    if not leg_detection_config.get("enabled", True):
        logger.debug("腿照识别功能已禁用")
        return False

    prompt = '请分析这张图片是否为实拍人类腿部照片，必须符合"美腿"定义，不能是男性。如果符合要求，直接回复"true"，否则回复"false"。不要解释，不要太多思考，只输出一个单词。'
    
    # 首次识别
    first_result = await call_siliconflow_api_async(context, base64_image, prompt)
    first_is_leg = first_result and "true" in first_result.lower()
    
    # 腿照，进行确认
    if first_is_leg:
        logger.debug("首次识别为腿照，进行第二次确认")
        second_result = await call_siliconflow_api_async(context, base64_image, prompt)
        second_is_leg = second_result and "true" in second_result.lower()
        
        # 结果不同，三次判断
        if not second_is_leg:
            logger.debug("两次识别结果不同，进行第三次判断")
            third_result = await call_siliconflow_api_async(context, base64_image, prompt)
            third_is_leg = third_result and "true" in third_result.lower()
        
            logger.debug(f"第三次识别结果: {'true' if third_is_leg else 'false'}")
            return bool(third_is_leg) if third_is_leg is not None else False
        
        # 两次都判断为腿照
        logger.debug("两次识别均为腿照，确认为腿照")
        return True
    
    # 首次判断不是腿照
    logger.debug("首次识别不是腿照")
    return False