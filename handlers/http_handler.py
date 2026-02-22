# handlers/http_handler.py
# 处理来自游戏服务器的HTTP回调

import json
from aiohttp import web
from logger_config import get_logger, log_exception
from core.bot_context import BotContext

logger = get_logger("HttpHandler")

async def handle_http_request(context: BotContext, request: web.Request) -> web.Response:
    """处理HTTP请求，将Minecraft相关功能转发给D-Cloud插件处理。"""
    try:
        local_port = request.transport.get_extra_info('sockname')[1]
        logger.debug(f"收到 HTTP 请求，端口: {local_port}")

        # 根据端口找到目标服务器配置
        target_server = None
        for server_name, server_config in context.config.get("servers", {}).items():
            if server_config["port"] == local_port:
                target_server = server_config
                break

        if not target_server:
            logger.warning("端口未配置")
            return web.Response(text="Port not configured", status=403)

        query = request.query
        mode = query.get('mode', '')
        
        # 检查是否为D-Cloud Minecraft插件处理的请求类型
        if mode in ['mcplayermsg', 'tpswarn']:
            # 尝试导入D-Cloud插件的HTTP处理器
            try:
                from plugins.D_Cloud_Minecraft.modules.http_handler import handle_http_request as dcloud_handle_request
                logger.debug("将请求转发给D-Cloud插件处理")
                return await dcloud_handle_request(context, request)
            except ImportError as e:
                logger.error(f"D-Cloud插件HTTP处理器导入失败: {e}")
                return web.Response(text="D-Cloud plugin not available", status=503)
        else:
            logger.debug(f"未识别的请求模式: {mode}")
            return web.Response(text="Unknown mode", status=400)

    except Exception as e:
        log_exception(logger, f"HTTP处理异常", e)
        return web.Response(text=str(e), status=500)