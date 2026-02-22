# commands/jrys_command.py
# 今日运势命令处理器

import asyncio
import os
import json
import random
import datetime
import aiohttp
import hashlib
from typing import Optional
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from utils.task_utils import create_monitored_task

logger = get_logger("JrysCommand")

# 运势数据配置
YUNSHI_DATA = {
    0: {"title": "渊厄（深渊级厄运）", "texts": [
        "黑云蔽日戾气生，妄动恐遭意外横\n谨言慎行守斋戒，静待阳升化七成",
        "天狗食月乱神魂，钱财饮食需谨慎\n黄庭静诵三百字，仙真或可护命门",
        "六爻俱凶血光随，大事缓决病速医\n幸有东北贵人至，赠符解围破危机"
    ]},
    1: {"title": "坎陷（坎卦级险境）", "texts": [
        "如履薄冰暗流藏，投资情爱需明辨\n玄武暗中施庇佑，慎终如始可渡关",
        "迷雾锁江小人生，文书反复戌时成\n佩玉挡灾引紫气，运程渐明见转机",
        "卷舌星动惹风波，晨拜朱雀化灾厄\n戌狗属相暗相助，谋略得当转危安"
    ]},
    2: {"title": "陷厄（沉陷级困局）", "texts": [
        "丧门照命忌远行，卯辰慎防无名盟\n戌狗赠赤玉髓佩，可挡灾星破阴霾",
        "病符侵体饮食忌，西南莫留锁元气\n亥时焚艾净宅后，天医祛病运势起",
        "勾陈缠身流言穿，巳未慎言钱财缘\n正东青衫老者现，指点迷津解困玄"
    ]},
    3: {"title": "蹇难（蹇卦级阻滞）", "texts": [
        "天罗地网藏刀锋，决策延七情装聋\n午时面西拜白.虎，铜铃三响破樊笼",
        "五鬼运财反噬凶，子寅紧闭防邪祟\n速请桃木刻鼠相，置于乾位镇厄空",
        "驿马倒悬行路难，五谷随身井卦言\n东北双鹊忽起舞，便是厄尽祥瑞显"
    ]},
    4: {"title": "中正（平衡之境）", "texts": [
        "阴阳和合运道平，守成持泰即功成\n虹霓贯东西时现，静待良机自有凭",
        "太极流转最安然，晨练卯时投土性\n故人忽传佳讯至，笑谈往昔续前缘",
        "星斗循轨循旧例，创新三思传机遇\n酉时双燕飞掠过，吉兆天机暗中藏"
    ]},
    5: {"title": "渐吉（渐进式祥兆）", "texts": [
        "三合局开旧债清，辰种财竹申小投\n红鸾初现含蓄应，运道渐开新财流",
        "文昌照曲正当时，朱砂点额增灵智\n西方捧书客偶遇，三问玄机得妙思",
        "玉堂贵人消恩怨，失物重现巽位显\n酉时备酒待客至，商机卦图暗中现"
    ]},
    6: {"title": "通明（通达级吉运）", "texts": [
        "禄存高照财门开，巳午投资翻番来\n分润马姓保长久，冷灶贵人送柴财",
        "驿马星动利远行，航班6/8最显灵\n异国鼠辈街头遇，竟是关键引路人",
        "天解星消法律业，文件三份印震歇\n亥时雨落洗净尘，新契前路自此开"
    ]},
    7: {"title": "鼎盛（巅峰级鸿运）", "texts": [
        "天乙贵人万事成，寅祭未提获重金\n双鱼跃门速购彩，所求皆得称人心",
        "将星坐镇展峥嵘，青绿战袍攻西锋\n戌时犬吠捷报至，竞技场上定输赢",
        "帝旺当头敢争锋，午地申科利不同\n分羹兔姓避亏空，盛极运道贯长虹"
    ]},
    8: {"title": "太和（终极祥瑞）", "texts": [
        "紫微开天门献瑞，三奇六合共相随\n功名正当九天月，鸾凤和鸣非梦哉",
        "河图洛书天降财，跨国冷门翻倍来\n红鸾星动良缘至，地涌甘泉金玉伴",
        "青龙盘柱文武彰，学术竞技破旧章\n亥子异梦先祖指，迷津得解镇八方"
    ]}
}

# 图片API设置
PORTRAIT_API = "https://rba.kanostar.top/portrait"
LANDSCAPE_API = "https://rba.kanostar.top/landscape"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 路径设置
# 资源目录改为 assets/image/YunShi
# 缓存目录改为 data/chache/YunShi
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_CACHE_DIR = os.path.join(SCRIPT_DIR, "..", "assets", "image", "YunShi")
TEMP_CACHE_PATH = os.path.join(SCRIPT_DIR, "..", "data", "chache", "YunShi", "temp.json")
LIMIT_FILE_PATH = os.path.join(SCRIPT_DIR, "..", "data", "jrys_bluearchive_limit.json")

# 速率限制配置
RATE_LIMITS = {
    "second": 3,  # 每秒限制
    "minute": 150,  # 每分钟限制
    "hour": 1500,  # 每小时限制
    "day": 4500  # 每天限制
}

# 确保目录存在
def ensure_directories():
    os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(TEMP_CACHE_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(LIMIT_FILE_PATH), exist_ok=True)

# 加载临时缓存
def load_temp_cache():
    ensure_directories()
    if os.path.exists(TEMP_CACHE_PATH):
        try:
            with open(TEMP_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 检查是否过了一天，如果过了就清空缓存
                if data.get("date") != datetime.date.today().isoformat():
                    data = {"date": datetime.date.today().isoformat(), "users": {}}
                return data
        except Exception as e:
            logger.error(f"加载临时缓存失败: {e}")
            return {"date": datetime.date.today().isoformat(), "users": {}}
    return {"date": datetime.date.today().isoformat(), "users": {}}

# 保存临时缓存
def save_temp_cache(data):
    try:
        with open(TEMP_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存临时缓存失败: {e}")

# 加载速率限制数据
def load_rate_limit_data():
    ensure_directories()
    if os.path.exists(LIMIT_FILE_PATH):
        try:
            with open(LIMIT_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 确保数据格式正确
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.error(f"加载速率限制数据失败: {e}")
    return []

# 保存速率限制数据
def save_rate_limit_data(data):
    try:
        with open(LIMIT_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存速率限制数据失败: {e}")

# 检查是否达到速率限制
def check_rate_limits():
    current_time = datetime.datetime.now()
    timestamps = load_rate_limit_data()
    
    # 过滤出有效的时间戳（保留最近24小时的）
    valid_timestamps = []
    for ts in timestamps:
        try:
            timestamp = datetime.datetime.fromisoformat(ts)
            # 只保留最近24小时的记录
            if (current_time - timestamp).total_seconds() < 86400:
                valid_timestamps.append(ts)
        except Exception as e:
            logger.error(f"解析时间戳失败: {e}")
    
    # 保存过滤后的数据
    save_rate_limit_data(valid_timestamps)
    
    # 检查各时间维度的限制
    for ts in valid_timestamps:
        timestamp = datetime.datetime.fromisoformat(ts)
        time_diff = (current_time - timestamp).total_seconds()
        
        # 检查每秒限制
        if time_diff < 1:
            if valid_timestamps.count(ts) >= RATE_LIMITS["second"]:
                return True
        
    # 检查每分钟限制
    minute_count = 0
    for ts in valid_timestamps:
        timestamp = datetime.datetime.fromisoformat(ts)
        if (current_time - timestamp).total_seconds() < 60:
            minute_count += 1
    if minute_count >= RATE_LIMITS["minute"]:
        return True
    
    # 检查每小时限制
    hour_count = 0
    for ts in valid_timestamps:
        timestamp = datetime.datetime.fromisoformat(ts)
        if (current_time - timestamp).total_seconds() < 3600:
            hour_count += 1
    if hour_count >= RATE_LIMITS["hour"]:
        return True
    
    # 检查每天限制
    day_count = len(valid_timestamps)
    if day_count >= RATE_LIMITS["day"]:
        return True
    
    return False

# 记录API调用
def record_api_call():
    current_time = datetime.datetime.now().isoformat()
    timestamps = load_rate_limit_data()
    timestamps.append(current_time)
    save_rate_limit_data(timestamps)

# 从API获取图片并保存
async def fetch_image_from_api(api_url):
    try:
        # 检查速率限制
        if check_rate_limits():
            logger.info("已达到API调用速率限制，使用缓存图片")
            return None
        
        # 确保目录存在
        ensure_directories()
        
        # 从API获取图片
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=HEADERS, timeout=10) as response:
                if response.status != 200:
                    logger.error(f"获取图片失败，状态码: {response.status}")
                    return None
                
                # 读取图片数据
                image_data = await response.read()
        
        # 生成唯一文件名
        md5_hash = hashlib.md5(image_data).hexdigest()
        file_extension = "png"  # 假设API返回PNG格式
        filename = f"{md5_hash}.{file_extension}"
        file_path = os.path.join(IMAGE_CACHE_DIR, filename)
        
        # 保存图片
        with open(file_path, "wb") as f:
            f.write(image_data)
        
        # 记录API调用
        record_api_call()
        
        logger.info(f"成功从API获取并保存图片: {filename}")
        return file_path
    except Exception as e:
        logger.error(f"获取图片时发生错误: {e}")
        return None

# 从缓存获取随机图片
def get_random_cached_image():
    ensure_directories()
    try:
        files = [f for f in os.listdir(IMAGE_CACHE_DIR) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
        if not files:
            return None
        return os.path.join(IMAGE_CACHE_DIR, random.choice(files))
    except Exception as e:
        logger.error(f"获取缓存图片失败: {e}")
        return None

# 获取运势图片（1/3概率使用原API，1/3概率使用新API，1/3概率使用缓存）
async def get_yunshi_image():
    # 随机选择图片来源
    choice = random.random()
    
    if choice < 1/3:
        # 1/3概率使用原API
        image_path = await fetch_image_from_api(PORTRAIT_API)
        # 如果API获取失败，尝试使用缓存
        if not image_path:
            image_path = get_random_cached_image()
        return image_path
    elif choice < 2/3:
        # 1/3概率使用新API
        image_path = await fetch_image_from_api(LANDSCAPE_API)
        # 如果API获取失败，尝试使用缓存
        if not image_path:
            image_path = get_random_cached_image()
        return image_path
    else:
        # 1/3概率使用缓存图片
        image_path = get_random_cached_image()
        # 如果缓存中没有图片，尝试从任一API获取
        if not image_path:
            # 随机选择一个API
            api_choice = random.choice([PORTRAIT_API, LANDSCAPE_API])
            image_path = await fetch_image_from_api(api_choice)
        return image_path

# 生成运势数据
def generate_yunshi(user_id):
    # 检查是否需要生成新的运势
    if random.random() < 0.7:
        a = random.randint(0, 2)
        b = random.randint(0, 2)
        c = random.randint(0, 2)
        d = random.randint(0, 2)
        level = a + b + c + d
    else:
        level = random.randint(0, 8)
        while True:
            a = random.randint(0, 2)
            b = random.randint(0, 2)
            c = random.randint(0, 2)
            d = level - (a + b + c)
            if 0 <= d <= 2:
                break
    text_index = random.randint(0, 2)
    stars = "★" * level + "☆" * (8 - level)

    return {
        "level": level,
        "text_index": text_index,
        "stars": stars,
        "detail": f"财运({a})+姻缘({b})+事业({c})+人品({d})"
    }

# 获取用户运势
def get_user_yunshi(user_id):
    cache = load_temp_cache()
    user_id_str = str(user_id)
    
    # 检查用户是否已有缓存
    if user_id_str in cache["users"]:
        return cache["users"][user_id_str]
    
    # 生成新的运势
    yunshi_data = generate_yunshi(user_id)
    cache["users"][user_id_str] = yunshi_data
    
    # 保存缓存
    save_temp_cache(cache)
    
    return yunshi_data

# 为了保持API兼容性，保留旧的函数名但使用新的实现
async def get_random_pool_image():
    return await get_yunshi_image()

# 移除图池刷新功能，保留函数以避免错误
def refresh_wallhaven_pool():
    logger.warning("图池刷新功能已移除，图片将自动从API获取并保存")

async def handle_jrys_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """
    处理 /jrys 命令，查询今日运势
    
    :param context: 机器人上下文，包含配置和WebSocket
    :param args: 命令参数列表（已去除命令名）
    :param user_id: 触发命令的用户QQ号
    :param group_id: 触发命令的群号
    :param server_name: 当前服务器名称
    :param kwargs: 其他可能的参数（如nickname、api_base、cmd_config、user_level等）
    :return: CommandResponse对象，包含要发送的响应
    """
    logger.info(f"用户 {user_id} 在群 {group_id} 执行了 /jrys 命令")
    
    # 发送处理中提示并保存消息ID
    processing_builder = MessageBuilder(context)
    processing_builder.set_group_id(group_id)
    processing_builder.set_user_id(user_id)
    processing_builder.add_at()
    processing_builder.add_text("🔮 正在为您查询今日运势，请稍候...")
    
    async def processing_callback(message_id: str):
        if message_id:
            # 启动后台任务处理运势查询，并传递处理中消息的ID
            create_monitored_task(
                process_jrys_request(context, args, user_id, group_id, message_id, **kwargs),
                name=f"JrysCommand_process_{user_id}_{group_id}"
            )
    
    processing_builder.set_callback(processing_callback)
    
    # 先发送处理中提示
    await processing_builder.send()
    
    # 返回None表示已经通过builder发送了消息
    return CommandResponse.none()

async def process_jrys_request(context: BotContext, args: list, user_id: str, group_id: str, processing_message_id: str, **kwargs) -> None:
    """在后台处理今日运势请求"""
    # 获取用户昵称
    nickname = kwargs.get('nickname', f"用户{user_id[-4:]}")
    
    # 普通的运势查询
    try:
        # 获取用户运势数据
        yunshi_data = get_user_yunshi(user_id)
        level_info = YUNSHI_DATA[yunshi_data["level"]]
        title = level_info["title"]
        text = level_info["texts"][yunshi_data["text_index"]]
        
        # 获取随机图片
        image_path = await get_random_pool_image()
        
        # 构建消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"阁下的今日运势是：\n{title}\n{yunshi_data['stars']}\n{text}\n{yunshi_data['detail']}\n")
        
        # 添加图片
        if image_path:
            builder.add_image(image_path)
        else:
            builder.add_text("（图片加载中...）\n")
        
        # 添加提示文字
        builder.add_text("仅供娱乐｜相信科学｜请勿迷信")
        
        # 发送最终结果
        await builder.send()
        
        # 尝试撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)
        
    except Exception as e:
        logger.error(f"查询今日运势失败: {e}")
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"❌ 查询今日运势失败：{str(e)}")
        await error_builder.send()
        
        # 尝试撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)

async def try_recall_processing_message(context: BotContext, processing_message_id: str) -> None:
    """尝试撤回处理中提示消息"""
    try:
        # 等待一段时间确保消息发送完成
        await asyncio.sleep(1)
        
        # 调用API撤回消息
        from utils.api_utils import call_onebot_api
        result = await call_onebot_api(
            context=context,
            action="delete_msg",
            params={"message_id": processing_message_id}
        )
        
        if not (result and result.get("success")):
            logger.warning(f"撤回处理中提示消息失败: {result}")
    except Exception as e:
        logger.warning(f"撤回处理中提示消息时发生异常: {e}")