# utils/task_utils.py
# 任务管理工具，包括定期清理数据库等任务

import asyncio
import time
from logger_config import get_logger

logger = get_logger("TaskUtils")

# 存储所有创建的任务引用，防止被垃圾回收
_background_tasks = set()

def create_monitored_task(coro, name: str = "Unnamed Task"):
    """
    创建一个受监控的后台任务
    
    :param coro: 协程对象
    :param name: 任务名称
    :return: Task对象
    """
    task = asyncio.create_task(coro, name=name)
    
    # 添加到集合中防止被垃圾回收
    _background_tasks.add(task)
    
    # 添加回调以在任务完成时从集合中移除
    def task_done_callback(task):
        _background_tasks.discard(task)
        try:
            if task.exception():
                logger.error(f"后台任务 '{name}' 发生未处理异常: {task.exception()}")
        except asyncio.CancelledError:
            # 任务被取消是正常的，不需要报告错误
            pass
    
    task.add_done_callback(task_done_callback)
    
    logger.debug(f"创建了后台任务: {name}")
    return task



# 初始化时启动后台任务
def start_background_tasks():
    """启动所有后台任务"""
    logger.info("后台任务已启动")