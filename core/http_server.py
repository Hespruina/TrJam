# core/http_server.py
# 负责创建和启动HTTP服务

import asyncio
import aiohttp
from aiohttp import web
from logger_config import get_logger, log_exception
from typing import Callable, Awaitable, List

logger = get_logger("HttpServer")

async def create_http_app(handler: Callable[[web.Request], Awaitable[web.Response]]) -> web.Application:
    """创建一个HTTP应用。"""
    app = web.Application()
    app.router.add_post('/', handler)
    return app

async def start_http_servers(context, handler: Callable[[web.Request], Awaitable[web.Response]]):
    """启动所有配置的HTTP服务器。"""
    ports = {s["port"] for s in context.config.get("servers", {}).values()}
    runners: List[web.AppRunner] = []

    for port in ports:
        app = await create_http_app(handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"HTTP服务已启动在端口 {port}")
        runners.append(runner)

    # runners 需要在程序生命周期内保持引用，这里简单返回，由调用者管理
    return runners