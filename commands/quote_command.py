# commands/quote_command.py
# 重构后的名言命令

import json
import time
import asyncio
from typing import Union, List, Dict, Any
from logger_config import get_logger
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.message_sender import MessageBuilder
from utils.task_utils import create_monitored_task
# 添加敏感词检测导入
from core.sensitive_word_manager import is_sensitive
# 添加信任管理器导入
from core.trust_manager import trust_manager

# 添加Quote功能所需的导入
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
import httpx
import os

logger = get_logger("QuoteCommand")

# 获取当前脚本目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# Quote功能的辅助函数
# 修复资源路径
def open_from_url(url: str):
    return Image.open(BytesIO(httpx.get(url).content))

def square_scale(image: Image.Image, height: int):
    old_width, old_height = image.size
    x = height / old_height
    width = int(old_width * x)
    return image.resize((width, height))

def wrap_text(text, chars_per_line=13):
    lines = [text[i:i + chars_per_line] for i in range(0, len(text), chars_per_line)]
    return '\n'.join(lines)

async def generate_quote_image(qq_number: str, message_content: str, sender_name: str) -> str:
    # 加载资源
    mask_path = os.path.join(script_dir, "../assets/quote/mask.png")
    mask = Image.open(mask_path).convert("RGBA")
    background = Image.new('RGBA', mask.size, (255, 255, 255, 255))
    
    ava_url = f"http://q2.qlogo.cn/headimg_dl?dst_uin={qq_number}&spec=640"
    head = open_from_url(ava_url).convert("RGBA")

    # 修复字体路径
    title_font = ImageFont.truetype(os.path.join(script_dir, "../assets/fonts/字魂59号-创粗黑.ttf"), size=36)
    desc_font = ImageFont.truetype(os.path.join(script_dir, "../assets/fonts/HarmonyOS Sans Black.ttf"), size=30)
    digit_font = ImageFont.truetype(os.path.join(script_dir, "../assets/fonts/Alte DIN 1451 Mittelschrift gepraegt.ttf"), size=36)
    emoji_font = ImageFont.truetype(os.path.join(script_dir, "../assets/fonts/SeGoe UI Emoji.ttf"), size=36)

    # 贴上头像并应用遮罩
    background.paste(square_scale(head, 640), (0, 0))
    background.paste(mask, (0, 0), mask)

    draw = ImageDraw.Draw(background)

    # 处理圆形头像
    mask_circle = Image.new("L", head.size, 0)
    draw_circle = ImageDraw.Draw(mask_circle)
    draw_circle.ellipse((0, 0, head.size[0], head.size[1]), fill=255)
    head.putalpha(mask_circle)

    # 文本换行处理
    text = wrap_text(message_content)
    x_offset = 640
    y_offset = 165

    # --- 关键修改开始 ---
    # 遍历文本中的每一个字符
    for char in text:
        # 根据字符类型选择字体和颜色
        if char.isdigit() or char == '.':
            font = digit_font
            fill_color = (255, 0, 0)
        elif ord(char) in range(0x1F600, 0x1F64F):  # Emoji 范围判断
            font = emoji_font
            fill_color = (255, 255, 255)
        else:
            font = title_font
            fill_color = (255, 255, 255)

        # --- 关键修复 ---
        # 如果是换行符，直接进行换行操作，不进行长度测量和绘制
        if char == '\n':
            x_offset = 640
            y_offset += 40
            continue  # 跳过本次循环，不执行后面的绘制和测量

        # 使用 ImageDraw.Draw.textlength() 方法计算字符宽度，兼容所有 Pillow 版本
        char_width = draw.textlength(char, font=font)

        # 检查是否需要换行
        if x_offset + char_width > mask.size[0]:
            x_offset = 640  # 重置到起始 X 坐标
            y_offset += 40  # Y 坐标下移一行

        # 在指定位置绘制字符
        draw.text((x_offset, y_offset), char, font=font, fill=fill_color)
        x_offset += char_width  # 更新 X 偏移量

        # 如果是换行符，则手动换行
        if char == '\n':
            x_offset = 640
            y_offset += 40
    # --- 关键修改结束 ---

    # 绘制昵称
    # 注意：这里也使用了 draw.textlength() 来计算昵称的宽度，以决定居中位置
    name_text = f"——{sender_name}"
    name_width = draw.textlength(name_text, font=desc_font)
    # 计算居中位置，640是头像宽度，mask.size[0]是总宽度
    name_x = (mask.size[0] + 640) // 2 - name_width // 2
    draw.text((name_x, 465), name_text, font=desc_font, fill=(112, 112, 112))

    # 合成最终图片
    nbg = Image.new('RGB', mask.size, (0, 0, 0))
    nbg.paste(background, (0, 0))

    # 转换为 base64
    buffer = BytesIO()
    nbg.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return img_base64

# 设置QUOTE_AVAILABLE为True，因为功能已内置
QUOTE_AVAILABLE = True
logger.info("Quote功能已内置加载")

# 内部处理名言功能的函数
async def handle_quote_internal(context: BotContext, user_id: str, group_id: str, raw_message: Union[str, List[Dict[str, Any]]], is_configured=True, account_id: int = None) -> bool:
    """内部处理名言功能的函数"""
    # 检查群组是否在信任列表中 (信任检查已由命令分发器完成，此处无需重复检查)
    # 信任检查逻辑已移至命令分发器中，此处不再重复检查

    # message参数已在dispatch_command中处理，这里直接执行

    if not QUOTE_AVAILABLE:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 名言功能未启用")
        await builder.send()
        return True

    replied_message_id = None
    if isinstance(raw_message, list):
        for segment in raw_message:
            if segment.get('type') == 'reply':
                replied_message_id = segment.get('data', {}).get('id')
                break

    if not replied_message_id:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ⚠️ 请引用一条消息后再使用此命令")
        await builder.send()
        return True

    msg_data = await call_onebot_api(
        context, 'get_msg',
        {'message_id': replied_message_id},
        account_id=account_id
    )
    if not msg_data or not msg_data.get("success"):
        # 无法获取消息，直接返回错误信息
        error_msg = msg_data.get("error", "未知错误") if msg_data else "API调用失败"
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ❌ 无法获取被引用的消息内容: {error_msg}")
        await builder.send()
        return True

    # 根据反撤回功能的解析方式，正确处理onebot API响应的嵌套数据结构
    if msg_data and msg_data.get("success") and msg_data["data"].get('status') == 'ok':
        # 获取实际的消息数据（三层嵌套结构）
        actual_msg_data = msg_data["data"]['data']
        
        # 确保获取到完整的消息内容
        msg_content = actual_msg_data.get('message', [])
        msg_sender = str(actual_msg_data.get('sender', {}).get('user_id', ''))
        msg_sender_nickname = actual_msg_data.get('sender', {}).get('card', '') or actual_msg_data.get('sender', {}).get('nickname', '未知用户')

        # 深度日志记录，帮助调试
        logger.debug(f"获取到的被引用消息数据: {json.dumps(actual_msg_data, ensure_ascii=False)}")
    else:
        # 如果数据结构不符合预期，输出错误并返回
        logger.error(f"API返回的数据结构不符合预期: {json.dumps(msg_data, ensure_ascii=False)}")
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 处理被引用消息失败：数据结构异常")
        await builder.send()
        return True

    if isinstance(msg_content, list):
        # 检查是否包含图片
        has_image = any(seg.get('type') == 'image' for seg in msg_content)
        if has_image:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(" ❌ 被引用的消息包含图片，不支持生成名言图片")
            await builder.send()
            return True
        
        # 提取文本内容，同时处理嵌套引用的情况
        text_content = ""
        for seg in msg_content:
            if seg.get('type') == 'text':
                # 提取文本内容
                text_seg = seg.get('data', {}).get('text', '')
                text_content += text_seg
                logger.debug(f"提取到文本段: {text_seg}")
            elif seg.get('type') == 'reply':
                # 处理嵌套引用
                logger.debug(f"检测到嵌套引用: {seg}")
                # 可以选择是否递归获取嵌套引用的消息
                # 这里我们选择直接跳过嵌套引用部分，只处理当前消息的文本
    else:
        # 如果消息内容不是列表，直接作为文本处理
        text_content = str(msg_content)
        logger.debug(f"消息内容为非列表类型: {text_content}")

    # 记录提取到的文本内容，便于调试
    logger.debug(f"最终提取到的文本内容: '{text_content}'")
    logger.debug(f"文本内容长度: {len(text_content)}, 去除空白后长度: {len(text_content.strip())}")
    
    # 添加敏感词检测 - 对消息发送者和指令发送者都进行检测
    # 检测被引用消息内容
    contains_sensitive, sensitive_word, sensitive_reason = is_sensitive(text_content)
    if contains_sensitive:
        logger.warning(f"检测到引用消息包含敏感词 '{sensitive_word}'，已阻止生成名言图片")
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ❌ 引用的消息包含敏感内容，无法生成名言图片")
        await builder.send()
        
        # 向report群发送报告
        await _send_sensitive_report(context, group_id, user_id, msg_sender, text_content, sensitive_word)
        return True
    
    # 检测指令发送者是否在敏感名单中
    user_contains_sensitive, user_sensitive_word, user_sensitive_reason = is_sensitive(user_id)
    if user_contains_sensitive:
        logger.warning(f"检测到指令发送者 {user_id} 在敏感名单中，已阻止生成名言图片")
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ❌ 指令发送者在敏感名单中，无法生成名言图片")
        await builder.send()
        
        # 向report群发送报告
        await _send_sensitive_report(context, group_id, user_id, msg_sender, f"指令发送者ID: {user_id}", user_sensitive_word)
        return True
    
    # 检测消息发送者是否在敏感名单中
    sender_contains_sensitive, sender_sensitive_word, sender_sensitive_reason = is_sensitive(msg_sender)
    if sender_contains_sensitive:
        logger.warning(f"检测到消息发送者 {msg_sender} 在敏感名单中，已阻止生成名言图片")
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ❌ 消息发送者在敏感名单中，无法生成名言图片")
        await builder.send()
        
        # 向report群发送报告
        await _send_sensitive_report(context, group_id, user_id, msg_sender, f"消息发送者ID: {msg_sender}", sender_sensitive_word)
        return True
    
    if not text_content.strip():
        # 确定消息为空的原因
        empty_reason = "消息内容为空或只包含空白字符"
        
        # 详细分析消息内容结构
        if isinstance(msg_content, list):
            # 记录消息段的数量和类型
            segment_types = [seg.get('type') for seg in msg_content]
            logger.debug(f"消息段类型分布: {segment_types}")
            
            # 检查是否包含非文本元素
            has_non_text = any(seg.get('type') != 'text' for seg in msg_content)
            if has_non_text:
                non_text_types = [seg.get('type') for seg in msg_content if seg.get('type') != 'text']
                empty_reason = f"消息中包含非文本元素({','.join(non_text_types)})，但没有可提取的文字内容"
        else:
            # 非列表类型的内容处理
            logger.debug(f"消息内容类型: {type(msg_content)}, 内容: {msg_content}")
        
        # 详细的错误信息，包含原始消息数据摘要
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ❌ 被引用的消息没有文字内容\n💡 原因：{empty_reason}\n💡 解决方法：请引用包含实际文字内容的消息")
        await builder.send()
        return True

    try:
        base64_img = await generate_quote_image(
            qq_number=msg_sender,
            message_content=text_content,
            sender_name=msg_sender_nickname
        )
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_image(f"base64://{base64_img}")
        await builder.send()
        return True
    except ImportError:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 名言功能未启用（Quote库导入失败）")
        await builder.send()
        return True
    except Exception as e:
        logger.error(f"生成名言图片时发生异常: {str(e)}", exc_info=True)
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ❌ 生成名言图片失败: {str(e)}")
        await builder.send()
        return True

async def _send_sensitive_report(context: BotContext, group_id: str, command_user_id: str, message_sender_id: str, content: str, sensitive_word: str):
    """发送敏感内容报告到配置的目标"""
    from utils.sensitive_word_reporter import SensitiveWordReporter
    try:
        # 构建额外信息
        additional_info = {
            "intercept_type": "名言命令",
            "command_user_id": command_user_id,
            "message_sender_id": message_sender_id
        }
        
        # 使用统一的报告处理器
        success = await SensitiveWordReporter.send_report(
            context, group_id, command_user_id, content, sensitive_word, 
            recalled=False, additional_info=additional_info
        )
        
        if success:
            logger.info("敏感内容报告发送成功")
        else:
            logger.warning("敏感内容报告发送失败")
            
    except Exception as e:
        logger.error(f"发送敏感内容报告时发生异常: {e}")

async def handle_quote_command(context: BotContext, args: list, user_id: str, group_id: str, nickname: str, **kwargs) -> None:
    """名言命令处理函数"""
    # 添加信任检查
    if not trust_manager.is_trusted_group(str(group_id)):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" 当前群未被信任，无法使用该功能。请联系 ROOT 用户了解如何信任本群。Root 用户 QQ：2711631445")
        await builder.send()
        return None
    
    raw_message = kwargs.get('raw_message') or []
    is_configured = kwargs.get('is_configured', True)
    account_id = kwargs.get('account_id')
    
    # 发送处理中提示并保存消息 ID
    processing_builder = MessageBuilder(context)
    processing_builder.set_group_id(group_id)
    processing_builder.set_user_id(user_id)
    processing_builder.add_at()
    processing_builder.add_text("📝 正在为您生成名言，请稍候...")
    
    async def processing_callback(message_id: str):
        if message_id:
            # 启动后台任务处理名言生成，并传递处理中消息的 ID 和账号 ID
            create_monitored_task(
                process_quote_request(context, user_id, group_id, raw_message, is_configured, message_id, account_id),
                name=f"QuoteCommand_process_{user_id}_{group_id}"
            )
    
    processing_builder.set_callback(processing_callback)
    
    # 发送处理中提示
    await processing_builder.send()
    
    # 返回 None 表示已处理，避免重复发送消息
    return None

async def process_quote_request(context: BotContext, user_id: str, group_id: str, raw_message: list, is_configured: bool, processing_message_id: str, account_id: int = None) -> None:
    """在后台处理名言请求"""
    try:
        await handle_quote_internal(context, user_id, group_id, raw_message, is_configured, account_id)
    except Exception as e:
        logger.error(f"处理名言请求时发生异常：{e}", exc_info=True)
        # 发送错误消息
        from utils.message_sender import MessageBuilder
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f" ❌ 生成名言图片时发生异常：{str(e)}")
        await builder.send()
    finally:
        # 撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id, account_id)

async def try_recall_processing_message(context: BotContext, processing_message_id: str, account_id: int = None) -> None:
    """尝试撤回处理中提示消息"""
    try:
        # 等待一段时间确保消息发送完成
        await asyncio.sleep(1)
        
        # 调用 API 撤回消息
        result = await call_onebot_api(
            context=context,
            action="delete_msg",
            params={"message_id": processing_message_id},
            account_id=account_id
        )
        
        if not (result and result.get("success")):
            logger.warning(f"撤回处理中提示消息失败: {result}")
    except Exception as e:
        logger.warning(f"撤回处理中提示消息时发生异常: {e}")

# 保留原来的 handle_quote 函数以兼容旧的调用方式，但简化其逻辑
async def handle_quote(context: BotContext, ws, user_id: str, group_id: str, message: str, raw_message: str, is_configured=True) -> bool:
    """处理名言功能（兼容旧调用方式）"""
    # 由于现在通过命令注册机制处理，这里可以简化为直接调用内部函数
    return await handle_quote_internal(context, user_id, group_id, raw_message, is_configured, account_id=None)