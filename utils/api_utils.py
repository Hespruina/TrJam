# utils/api_utils.py
# 重构后的API调用工具，统一返回格式

import asyncio
import aiohttp
from typing import Dict, Any, Optional
from logger_config import get_logger, log_exception, log_api_request

logger = get_logger("ApiUtils")

async def safe_api_request(url: str, method: str = 'get', params: dict = None, json_data: dict = None, headers: dict = None, timeout: int = None, context: Any = None) -> Optional[Dict[str, Any]]:
    """
    安全的API请求函数，处理各种异常情况
    :param url: 请求URL
    :param method: 请求方法 ('get' 或 'post')
    :param params: GET 参数
    :param json_data: POST JSON 数据
    :param headers: 请求头
    :param timeout: 超时时间(秒)，如果为None且提供了context，则从配置读取
    :param context: BotContext对象，用于获取配置中的默认超时设置
    :return: 响应数据(字典)或None(失败)
    """
    try:
        # 如果未指定超时时间但提供了context，尝试从配置读取默认超时
        if timeout is None and context is not None:
            timeout = context.get_config_value('default_api_timeout', 120)
        # 如果仍然没有超时值，使用默认值
        if timeout is None:
            timeout = 120
            
        async with aiohttp.ClientSession() as session:
            request_kwargs = {
                'timeout': aiohttp.ClientTimeout(total=timeout),
                'headers': headers or {}
            }
            if method.lower() == 'get':
                request_kwargs['params'] = params
                async with session.get(url, **request_kwargs) as resp:
                    return await _process_response(resp, url, method)
            elif method.lower() == 'post':
                if json_data is not None:
                    request_kwargs['json'] = json_data
                else:
                    request_kwargs['params'] = params
                async with session.post(url, **request_kwargs) as resp:
                    return await _process_response(resp, url, method)
            else:
                log_exception(logger, f"不支持的请求方法", Exception(f"请求方法 {method} 不被支持"))
                return None
    except asyncio.TimeoutError:
        log_exception(logger, f"API请求超时", Exception(f"请求 {url} 超时 ({timeout}秒)"))
        return {"success": False, "error": f"请求超时 ({timeout}秒)"}
    except aiohttp.ClientError as e:
        log_exception(logger, f"网络请求异常: {url}", e)
        return {"success": False, "error": f"网络错误: {str(e)}"}
    except Exception as e:
        log_exception(logger, f"API处理异常: {url}", e)
        return {"success": False, "error": f"未知错误: {str(e)}"}

async def _process_response(resp: aiohttp.ClientResponse, url: str, method: str) -> Optional[Dict[str, Any]]:
    """
    处理HTTP响应
    :param resp: aiohttp响应对象
    :return: 标准化响应字典 { "success": bool, "data": dict, "error": str }
    """
    success = resp.status == 200
    log_api_request(logger, url, method=method, success=success, status_code=resp.status)

    try:
        if resp.status == 200:
            try:
                data = await resp.json()
                return {"success": True, "data": data, "error": None}
            except aiohttp.ContentTypeError:
                text_data = await resp.text()
                log_exception(logger, f"API返回非JSON响应: {url}", Exception(f"响应内容: {text_data[:100]}..."))
                return {"success": False, "data": None, "error": f"非JSON响应: {text_data[:100]}..."}
            except Exception as e:
                log_exception(logger, f"解析JSON响应异常: {url}", e)
                return {"success": False, "data": None, "error": f"JSON解析失败: {str(e)}"}
        else:
            # 尝试解析错误响应为JSON
            try:
                error_data = await resp.json()
                # 提取友好的错误消息，而不是直接显示整个JSON对象
                if isinstance(error_data, dict):
                    if 'error' in error_data:
                        # 如果有error字段，使用它作为错误消息
                        error_msg = f"{error_data['error']}"
                    elif 'message' in error_data:
                        # 如果有message字段，使用它
                        error_msg = f"{error_data['message']}"
                    else:
                        # 否则使用简单状态码提示，不暴露内部结构
                        error_msg = f"请求失败，状态码: {resp.status}"
                else:
                    error_msg = f"请求失败，状态码: {resp.status}"
                return {"success": False, "data": error_data, "error": error_msg}
            except aiohttp.ContentTypeError:
                error_text = await resp.text()
                error_msg = f"请求失败: {error_text[:100]}..."
                return {"success": False, "data": None, "error": error_msg}
            except Exception as e:
                error_msg = f"无法读取响应: {str(e)}"
                return {"success": False, "data": None, "error": error_msg}
    except Exception as e:
        log_exception(logger, f"处理响应异常: {url}", e)
        return {"success": False, "data": None, "error": f"处理响应失败: {str(e)}"}

# 为BotContext提供的便捷API调用函数
async def call_api(context: Any, params=None, api_base=None) -> Optional[Dict[str, Any]]:
    """调用外部API"""
    if not api_base:
        logger.error("API基础URL未提供")
        return {"success": False, "error": "API基础URL未提供"}

    return await safe_api_request(api_base, method='get', params=params, context=context)

async def call_onebot_api(context: Any, action, params=None) -> Optional[Dict[str, Any]]:
    """调用 onebot OneBot API"""
    onebot_api_base = context.get_config_value('onebot_api_base')
    if not onebot_api_base:
        logger.error("onebot API Base URL 未配置")
        return {"success": False, "error": "onebot API Base URL 未配置"}

    api_url = f"{onebot_api_base.rstrip('/')}/{action.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {context.get_config_value('onebot_access_token')}",
        "Content-Type": "application/json",
        "User-Agent": "QQBot/1.0"
    }
    
    # 添加Debug级别日志，记录请求详情
    logger.debug(f"onebot API请求: 操作={action}, URL={api_url}")
    if params:
        # 过滤敏感信息后记录参数
        from logger_config import _redact_sensitive_info
        redacted_params = _redact_sensitive_info(params)
        logger.debug(f"onebot API请求参数: {redacted_params}")
    
    # 构建完整请求负载
    request_payload = {
        'url': api_url,
        'method': 'post',
        'headers': headers,
        'json_data': params or {}
    }
    
    # 记录原始构建的请求负载debug日志（过滤敏感信息）
    from logger_config import _redact_sensitive_info
    redacted_payload = _redact_sensitive_info(request_payload)
    logger.debug(f"onebot API原始请求负载: {redacted_payload}")
    
    # 发送请求
    response = await safe_api_request(**request_payload, context=context)
    
    # 添加Debug级别日志，记录响应详情
    if response:
        if response.get('success'):
            logger.debug(f"onebot API响应成功: 操作={action}, 状态=成功")
            # 对于成功响应，可以记录更详细的数据（根据需要）
            logger.debug(f"onebot API响应数据: {response.get('data')}")
        else:
            logger.debug(f"onebot API响应失败: 操作={action}, 错误={response.get('error')}")
    else:
        logger.debug(f"onebot API请求无响应: 操作={action}")
    
    return response
