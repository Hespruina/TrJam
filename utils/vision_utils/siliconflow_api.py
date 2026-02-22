# utils/vision_utils/siliconflow_api.py
# 硅基流动API调用

import asyncio
import aiohttp
import json
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from typing import Optional

logger = get_logger("SiliconFlowAPI")

async def call_siliconflow_api_async(
    context: BotContext,
    base64_image: str,
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[str]:
    """异步调用 SiliconFlow API 进行图像分析"""
    # 检查全局LLM开关
    if not context.get_config_value("llm_enabled", False):
        logger.debug("LLM功能已禁用，跳过图像分析")
        return None
        
    try:
        # 从配置中获取API信息
        ai_vision_config = context.get_config_value("ai_vision", {})
        api_key = api_key or ai_vision_config.get("api_key") if ai_vision_config else None
        model = model or ai_vision_config.get("model", "Qwen/Qwen2.5-VL-32B-Instruct") if ai_vision_config else "Qwen/Qwen2.5-VL-32B-Instruct"
        base_url = ai_vision_config.get("base_url", "https://api.siliconflow.cn/v1/chat/completions") if ai_vision_config else "https://api.siliconflow.cn/v1/chat/completions"

        if not api_key:
            logger.error("未配置硅基流动API密钥")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 构建符合Data URL标准的图像URL
        image_url_str = f"data:image/jpeg;base64,{base64_image}"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url_str,
                                "detail": "low"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "stream": True  # 启用流式输出
        }

        # 从配置中读取超时时间
        timeout_config = ai_vision_config.get('timeout', {})
        total_timeout = timeout_config.get('total', 120)  # 默认总超时120秒
        connect_timeout = timeout_config.get('connect', 10)  # 默认连接超时10秒
        timeout = aiohttp.ClientTimeout(total=total_timeout, connect=connect_timeout)
        
        # 不再重试，只调用一次
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(base_url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    
                    # 处理流式响应
                    full_response = ""
                    async for line in response.content:
                        if line:
                            decoded_line = line.decode('utf-8').strip()
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]  # 移除 "data: " 前缀
                                if data_str == "[DONE]":
                                    break
                                
                                try:
                                    data = json.loads(data_str)
                                    if "choices" in data and len(data["choices"]) > 0:
                                        delta = data["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            full_response += content
                                            # 一旦收到有效内容，就认为连接是成功的
                                            if not full_response.strip():  # 第一次收到内容时记录
                                                logger.debug("开始接收流式响应")
                                except json.JSONDecodeError:
                                    # 忽略解析错误的行
                                    continue
                    
                    # 返回完整响应
                    return full_response.strip() if full_response else None
                    
        except asyncio.TimeoutError:
            logger.error("硅基流动API调用超时，不再重试")
            return None
        except aiohttp.ClientError as e:
            log_exception(logger, "硅基流动API请求失败，不再重试", e)
            return None

    except Exception as e:
        log_exception(logger, "硅基流动API处理异常", e)
        return None