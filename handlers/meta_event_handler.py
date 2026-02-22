# handlers/meta_event_handler.py
# 处理元事件，如生命周期事件和心跳事件

import time
import asyncio
from logger_config import get_logger

logger = get_logger("MetaEventHandler")

# 存储心跳检查任务
_heartbeat_tasks = {}

class MetaEventType:
    """元事件类型定义"""
    LIFECYCLE = "lifecycle"
    HEARTBEAT = "heartbeat"
    
    class Lifecycle:
        CONNECT = "connect"

class MetaEventHandler:
    """处理元事件，包括连接和心跳事件"""
    
    def __init__(self):
        self.last_heartbeat_time = {}
        self.heartbeat_intervals = {}
        self.heartbeat_checking = {}

    async def handle_meta_event(self, context, event: dict):
        """处理元事件"""
        meta_event_type = event.get("meta_event_type")
        logger.debug(f"收到元事件: {meta_event_type}")
        
        if meta_event_type == MetaEventType.LIFECYCLE:
            sub_type = event.get("sub_type")
            if sub_type == MetaEventType.Lifecycle.CONNECT:
                self_id = event.get("self_id")
                logger.info(f"Bot {self_id} 连接成功")
                
        elif meta_event_type == MetaEventType.HEARTBEAT:
            status = event.get("status", {})
            good = status.get("good", False)
            online = status.get("online", False)
            self_id = event.get("self_id", "unknown")
            
            logger.debug(f"收到Bot {self_id} 的心跳事件 - good: {good}, online: {online}")
            
            # 更新多连接管理器中的心跳状态
            if hasattr(context, 'multi_ws_manager'):
                # 将interval信息也传递给update_heartbeat方法
                if "interval" in event:
                    status["interval"] = event["interval"]
                    logger.debug(f"传递心跳间隔信息给账号 {self_id}: {event['interval']}ms")
                context.multi_ws_manager.update_heartbeat(self_id, status)
            
            if good and online:
                # 更新最后一次心跳时间
                self.last_heartbeat_time[self_id] = time.time()
                
                # 获取心跳间隔（毫秒转秒）
                interval_ms = event.get("interval", 15000)  # 默认15秒
                interval = interval_ms / 1000
                self.heartbeat_intervals[self_id] = interval
                
                logger.debug(f"Bot {self_id} 心跳状态良好，间隔: {interval_ms}ms")
                
                # 如果还没有启动心跳检查任务，则启动一个
                if not self.heartbeat_checking.get(self_id, False):
                    task = asyncio.create_task(self._check_heartbeat(context, self_id))
                    _heartbeat_tasks[self_id] = task
                    self.heartbeat_checking[self_id] = True
                    logger.debug(f"为Bot {self_id} 启动心跳检查任务")
            else:
                logger.warning(f"Bot {self_id} 状态异常！good: {good}, online: {online}")
        else:
            logger.debug(f"未处理的元事件类型: {meta_event_type}")

    async def _check_heartbeat(self, context, bot_id):
        """检查心跳状态的任务"""
        logger.debug(f"开始检查Bot {bot_id} 的心跳状态")
        while True:
            try:
                # 获取心跳间隔
                interval = self.heartbeat_intervals.get(bot_id, 15)  # 默认15秒
                
                # 等待心跳间隔时间
                await asyncio.sleep(interval)
                
                # 检查最后一次心跳时间
                last_time = self.last_heartbeat_time.get(bot_id, 0)
                current_time = time.time()
                
                # 如果超过两倍心跳间隔没有收到心跳，则认为连接可能断开
                if current_time - last_time > interval * 2:
                    logger.error(f"Bot {bot_id} 可能发生了连接断开，被下线，或者OneBot服务卡死！")
                    # 可以在这里添加重连逻辑或其他处理
                    self.heartbeat_checking[bot_id] = False
                    break
                else:
                    logger.debug(f"Bot {bot_id} 心跳正常")
                    
            except asyncio.CancelledError:
                logger.info(f"Bot {bot_id} 的心跳检查任务被取消")
                break
            except Exception as e:
                logger.error(f"检查Bot {bot_id} 心跳时发生异常: {e}")
                # 出现异常时继续检查
                await asyncio.sleep(5)  # 等待5秒再继续

# 创建全局实例
meta_event_handler = MetaEventHandler()

async def handle_meta_event(context, event: dict):
    """处理元事件的全局函数"""
    await meta_event_handler.handle_meta_event(context, event)