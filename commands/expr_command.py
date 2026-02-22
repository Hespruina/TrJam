# commands/expr_command.py
# 处理 /expr 命令和中文命令（查快递、快递、单号、快递单号）

import asyncio
import httpx
import json
import os
from datetime import datetime
from logger_config import get_logger
from core.bot_context import BotContext

# cnm那个天才的代码写错导入了
import collections
import collections.abc
collections.MutableSet = collections.abc.MutableSet
collections.MutableMapping = collections.abc.MutableMapping
collections.MutableSequence = collections.abc.MutableSequence

logger = get_logger("ExprCommand")

# 快递提醒文件路径
EXPRESS_REMIND_FILE = "data/express_command.json"

# 确保data目录存在
os.makedirs("data", exist_ok=True)

# 初始化快递提醒文件
if not os.path.exists(EXPRESS_REMIND_FILE):
    with open(EXPRESS_REMIND_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

async def load_express_reminders():
    """加载快递提醒数据"""
    try:
        with open(EXPRESS_REMIND_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载快递提醒数据失败: {e}")
        return {}

async def save_express_reminders(data):
    """保存快递提醒数据"""
    try:
        with open(EXPRESS_REMIND_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存快递提醒数据失败: {e}")

async def check_express_updates(context: BotContext):
    """检查快递状态更新"""
    reminders = await load_express_reminders()
    updated_reminders = {}
    
    for mail_no, info in reminders.items():
        try:
            # 调用快递查询API
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://assistant-express.vivo.com.cn/pkginfobymn", params={"mailNo": mail_no, "imei": "1"}, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            
            # 解析API返回结果
            if not data or not isinstance(data, list):
                logger.error(f"快递查询API返回数据格式错误: {mail_no}")
                continue
            
            result = data[0]
            if result.get("retcode") != 0:
                logger.error(f"快递查询失败: {mail_no}, {result.get('message', '未知错误')}")
                continue
            
            express_data = result.get("data", {})
            if not express_data:
                logger.error(f"未查询到快递信息: {mail_no}")
                continue
            
            # 提取快递信息
            logistics_status = express_data.get("logisticsStatusDesc", "未知状态")
            full_trace_detail = express_data.get("fullTraceDetail", [])
            
            # 检查是否有最新的物流信息
            if full_trace_detail:
                latest_time = full_trace_detail[0].get("time", "")
                latest_desc = full_trace_detail[0].get("desc", "")
                
                # 检查时间是否更新
                if latest_time != info.get("last_update_time"):
                    # 构建提醒消息
                    reply = f"📦 快递状态更新提醒\n"
                    reply += f"单号：{mail_no}\n"
                    reply += f"状态：{logistics_status}\n"
                    reply += f"最新信息：{latest_desc}\n"
                    reply += f"时间：{latest_time}\n"
                    
                    # 尝试发送群消息
                    group_id = info.get("group_id")
                    user_id = info.get("user_id")
                    
                    sent = False
                    if group_id and user_id:
                        try:
                            # 群消息添加艾特
                            at_reply = f"[CQ:at,qq={user_id}] " + reply
                            await context.send_group_message(group_id, at_reply)
                            sent = True
                        except Exception as e:
                            logger.error(f"发送群消息失败: {e}")
                    
                    # 如果群消息发送失败，尝试私信
                    if not sent and user_id:
                        try:
                            await context.send_private_message(user_id, reply)
                            sent = True
                        except Exception as e:
                            logger.error(f"发送私信失败: {e}")
                    
                    # 如果都失败，删除此单号
                    if not sent:
                        logger.error(f"发送提醒失败，删除单号: {mail_no}")
                        continue
                    
                    # 更新最后更新时间
                    info["last_update_time"] = latest_time
            
            # 检查是否已签收
            if "已签收" in logistics_status:
                # 构建提醒消息
                reply = f"📦 快递已签收提醒\n"
                reply += f"单号：{mail_no}\n"
                reply += f"状态：{logistics_status}\n"
                if full_trace_detail:
                    latest_desc = full_trace_detail[0].get("desc", "")
                    latest_time = full_trace_detail[0].get("time", "")
                    reply += f"签收信息：{latest_desc}\n"
                    reply += f"签收时间：{latest_time}\n"
                reply += "\n✅ 已自动取消此单号的提醒"
                
                # 尝试发送群消息
                group_id = info.get("group_id")
                user_id = info.get("user_id")
                
                sent = False
                if group_id and user_id:
                    try:
                        # 群消息添加艾特
                        at_reply = f"[CQ:at,qq={user_id}] " + reply
                        await context.send_group_message(group_id, at_reply)
                        sent = True
                    except Exception as e:
                        logger.error(f"发送群消息失败: {e}")
                
                # 如果群消息发送失败，尝试私信
                if not sent and user_id:
                    try:
                        await context.send_private_message(user_id, reply)
                        sent = True
                    except Exception as e:
                        logger.error(f"发送私信失败: {e}")
                
                # 无论是否发送成功，都删除此单号
                continue
            
            # 保留未签收的单号
            updated_reminders[mail_no] = info
            
        except Exception as e:
            logger.error(f"检查快递更新失败: {mail_no}, {e}")
            # 保留单号，下次再试
            updated_reminders[mail_no] = info
    
    # 保存更新后的提醒数据
    await save_express_reminders(updated_reminders)

# 启动定时任务
async def start_express_check_task(context: BotContext):
    """启动快递检查定时任务"""
    while True:
        try:
            await check_express_updates(context)
        except Exception as e:
            logger.error(f"定时任务执行失败: {e}")
        # 每20分钟检查一次
        await asyncio.sleep(1200)

async def handle_expr_command(context: BotContext, args: list, user_id: str, group_id: str, command: str, **kwargs) -> str:
    """处理快递查询命令。"""
    if not args:
        return "❌ 参数错误，格式：/expr <快递单号> 或 查快递 <快递单号> 或 /expr mind <快递单号>"
    
    # 检查是否是mind参数
    if args[0] == "mind":
        if len(args) < 2:
            return "❌ 参数错误，格式：/expr mind <快递单号>"
        
        mail_no = args[1]
        if not mail_no:
            return "❌ 请输入有效的快递单号"
        
        try:
            # 调用快递查询API
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://assistant-express.vivo.com.cn/pkginfobymn", params={"mailNo": mail_no, "imei": "1"}, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            
            # 解析API返回结果
            if not data or not isinstance(data, list):
                return "❌ API返回数据格式错误"
            
            result = data[0]
            if result.get("retcode") != 0:
                message = result.get("message", "查询失败")
                return f"❌ {message}"
            
            express_data = result.get("data", {})
            if not express_data:
                return "❌ 未查询到快递信息"
            
            # 提取快递信息
            logistics_status = express_data.get("logisticsStatusDesc", "未知状态")
            full_trace_detail = express_data.get("fullTraceDetail", [])
            
            # 获取最后更新时间
            last_update_time = ""
            if full_trace_detail:
                last_update_time = full_trace_detail[0].get("time", "")
            
            # 加载现有提醒数据
            reminders = await load_express_reminders()
            
            # 添加或更新提醒
            reminders[mail_no] = {
                "group_id": group_id,
                "user_id": user_id,
                "last_update_time": last_update_time,
                "add_time": datetime.now().isoformat()
            }
            
            # 保存提醒数据
            await save_express_reminders(reminders)
            
            # 构建回复消息
            reply = f"✅ 快递提醒已添加\n"
            reply += f"单号：{mail_no}\n"
            reply += f"当前状态：{logistics_status}\n"
            reply += "\n🤖 机器人将每20分钟检查一次快递状态，有更新会及时提醒您"
            
            # 启动定时任务（如果还没启动）
            if not hasattr(handle_expr_command, "task_started"):
                handle_expr_command.task_started = True
                asyncio.create_task(start_express_check_task(context))
                logger.info("快递检查定时任务已启动")
            
            return reply
            
        except httpx.RequestError as e:
            logger.error(f"快递查询API请求失败: {e}")
            return "❌ 网络请求失败，请稍后重试"
        except Exception as e:
            logger.error(f"快递提醒添加失败: {e}")
            return "❌ 添加提醒失败，请稍后重试"
    
    # 普通查询逻辑
    mail_no = args[0]
    if not mail_no:
        return "❌ 请输入有效的快递单号"
    
    try:
        # 调用快递查询API
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://assistant-express.vivo.com.cn/pkginfobymn", params={"mailNo": mail_no, "imei": "1"}, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        
        # 解析API返回结果
        if not data or not isinstance(data, list):
            return "❌ API返回数据格式错误"
        
        result = data[0]
        if result.get("retcode") != 0:
            message = result.get("message", "查询失败")
            return f"❌ {message}"
        
        express_data = result.get("data", {})
        if not express_data:
            return "❌ 未查询到快递信息"
        
        # 提取快递信息
        mail_no = express_data.get("mailNo", mail_no)
        cp_code = express_data.get("cpCode", "未知快递公司")
        logistics_status = express_data.get("logisticsStatusDesc", "未知状态")
        full_trace_detail = express_data.get("fullTraceDetail", [])
        
        # 构建回复消息
        reply = f"快递查询结果\n"
        reply += f"单号：{mail_no}\n"
        reply += f"快递公司：{cp_code}\n"
        reply += f"物流状态：{logistics_status}\n"
        
        if full_trace_detail:
            reply += "\n最新物流信息：\n"
            # 只显示最新的几条物流信息
            for i, trace in enumerate(full_trace_detail[:3]):
                desc = trace.get("desc", "")
                time = trace.get("time", "")
                city = trace.get("city", "")
                if desc:
                    reply += f"{i+1}. {desc}\n"
                    if time:
                        reply += f"   时间：{time}\n"
                    if city:
                        reply += f"   地点：{city}\n"
        
        return reply
        
    except httpx.RequestError as e:
        logger.error(f"快递查询API请求失败: {e}")
        return "❌ 网络请求失败，请稍后重试"
    except Exception as e:
        logger.error(f"快递查询处理异常: {e}")
        return "❌ 查询过程中发生错误"
