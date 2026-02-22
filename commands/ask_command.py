import asyncio
import json
import random
from typing import List, Dict, Optional
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from utils.task_utils import create_monitored_task
from utils.language_utils import select_relevant_answers, generate_answer_explanation

# 添加answer_book功能所需的导入
import base64
from jinja2 import Template
from playwright.async_api import async_playwright, Page

# 从core.browser_manager导入浏览器管理器
from core.browser_manager import browser_manager

# 添加异步文件操作支持
import aiofiles

logger = get_logger("AskCommand")

# 固定星星位置
random.seed(42)
FIXED_STARS: List[tuple] = [
    (random.uniform(0, 100), random.uniform(0, 100), 0.5 + random.uniform(0, 2.5))
    for _ in range(150)
]

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>答案之书</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            width: 600px;
            height: 900px;
            background: linear-gradient(135deg, #1a0633, #2d0b5e, #4b0082);
            color: #e6d7ff;
            font-family: 'HarmonyOS Sans SC', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            position: relative;
        }
        .stars {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
        }
        .star {
            position: absolute;
            background-color: white;
            border-radius: 50%;
        }
        .container {
            text-align: center;
            z-index: 2;
            max-width: 500px;
            padding: 30px;
            background: rgba(26, 6, 51, 0.7);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            box-shadow: 0 0 30px rgba(138, 43, 226, 0.6);
            border: 1px solid rgba(147, 112, 219, 0.5);
        }
        h1 {
            font-size: 2.4rem;
            margin-bottom: 25px;
            text-shadow: 0 0 15px rgba(186, 85, 211, 0.8);
            letter-spacing: 2px;
        }
        .hexagram {
            width: 90px;
            height: 90px;
            margin: 0 auto 25px;
            position: relative;
        }
        .hexagram::before,
        .hexagram::after {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: 2px solid rgba(230, 215, 255, 0.6);
            box-sizing: border-box;
        }
        .hexagram::before { transform: rotate(30deg); }
        .hexagram::after { transform: rotate(-30deg); }
        .answer-box {
            background: rgba(18, 2, 36, 0.85);
            padding: 22px;
            border-radius: 15px;
            margin-top: 20px;
            border: 1px solid rgba(147, 112, 219, 0.4);
            box-shadow: inset 0 0 15px rgba(106, 13, 173, 0.5);
        }
        .answer-text {
            font-size: 1.7rem;
            line-height: 1.6;
            margin: 0;
            text-shadow: 0 0 10px rgba(186, 85, 211, 0.7);
        }
        .subtitle {
            font-size: 1.05rem;
            color: #c2a7ff;
            margin-top: 12px;
            font-style: italic;
        }

        /* 水印样式 */
        .watermark {
            position: absolute;
            bottom: 15px;
            right: 15px;
            font-size: 0.75rem;
            color: rgba(230, 215, 255, 0.5);
            text-align: right;
            line-height: 1.3;
            z-index: 3;
            pointer-events: none;
            font-weight: normal;
        }
    </style>
</head>
<body>
    <div class="stars">
        {% for x, y, size in fixed_stars %}
        <div class="star" style="
            left: {{ x }}%;
            top: {{ y }}%;
            width: {{ size }}px;
            height: {{ size }}px;
            opacity: {{ opacities[loop.index0] }};
        "></div>
        {% endfor %}
    </div>
    <div class="container">
        <h1>答案之书</h1>
        <div class="hexagram"></div>
        <div class="answer-box">
            <p class="answer-text">{{ main_text }}</p>
            <p class="subtitle">——{{ subtitle_text }}</p>
        </div>
    </div>
    <div class="watermark">ZHRrobot 3.0<br>zhrhello.top</div>
</body>
</html>
'''

async def generate_answer_book_image_base64(main_text: str, subtitle_text: str) -> str:
    page: Optional[Page] = None
    try:
        opacities = [round(0.2 + random.random() * 0.8, 3) for _ in FIXED_STARS]

        template = Template(HTML_TEMPLATE)
        html_content = template.render(
            main_text=main_text,
            subtitle_text=subtitle_text,
            fixed_stars=FIXED_STARS,
            opacities=opacities
        )

        # 使用共享的浏览器管理器获取页面
        page = await browser_manager.get_page()
        await page.set_viewport_size({"width": 600, "height": 900})
        await page.set_content(html_content)
        await page.wait_for_timeout(500)  # 减少等待时间，因为浏览器已经预热
        screenshot_bytes = await page.screenshot(type='png')

        return base64.b64encode(screenshot_bytes).decode('utf-8')
        
    finally:
        # 确保页面被关闭
        if page:
            await browser_manager.close_page(page)

async def generate_answer_book_image_data_uri(main_text: str, subtitle_text: str) -> str:
    b64 = await generate_answer_book_image_base64(main_text, subtitle_text)
    return f"data:image/png;base64,{b64}"

async def handle_ask_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """
    处理 /ask 命令，使用答案之书回答问题
    
    :param context: 机器人上下文，包含配置和WebSocket
    :param args: 命令参数列表（已去除命令名）
    :param user_id: 触发命令的用户QQ号
    :param group_id: 触发命令的群号
    :param kwargs: 其他可能的参数
    :return: CommandResponse对象，包含要发送的响应
    """
    logger.info(f"用户 {user_id} 在群 {group_id} 执行了 /ask 命令")
    
    # 检查是否提供了问题
    if not args:
        return CommandResponse.text("❌ 请提供您的问题，例如：/ask 我应该换工作吗？")
    
    question = ' '.join(args)
    
    # 发送处理中提示
    processing_builder = MessageBuilder(context)
    processing_builder.set_group_id(group_id)
    processing_builder.set_user_id(user_id)
    processing_builder.add_at()
    processing_builder.add_text("🔮 正在为您查询答案之书，请稍候...")
    
    async def processing_callback(message_id: str):
        if message_id:
            # 启动后台任务处理答案查询，并传递处理中消息的ID
            create_monitored_task(
                process_ask_request(context, question, user_id, group_id, message_id),
                name=f"AskCommand_process_{user_id}_{group_id}"
            )
    
    processing_builder.set_callback(processing_callback)
    
    # 发送处理中提示
    await processing_builder.send()
    
    # 返回none表示已经通过builder发送了消息
    return CommandResponse.none()

async def process_ask_request(context: BotContext, question: str, user_id: str, group_id: str, processing_message_id: str):
    """
    在后台处理ask请求的耗时操作
    
    :param context: 机器人上下文
    :param question: 用户的问题
    :param user_id: 用户ID
    :param group_id: 群ID
    :param processing_message_id: 处理中消息的ID，用于后续撤回
    """
    try:
        # 加载答案库
        answers_pool = await load_answers(context.config.get("assets_path", "assets") + "/text/answerbook.json")
        
        # 随机抽取 5 个答案
        candidates = get_random_answers(answers_pool, 5)
        
        # 使用 language_utils 模块中的函数让AI筛选可用答案
        # 添加超时控制，避免AI调用阻塞过长时间
        try:
            relevant_indices = await asyncio.wait_for(
                select_relevant_answers(question, candidates, context.config),
                timeout=30  # 设置30秒超时
            )
        except asyncio.TimeoutError:
            logger.warning(f"AI 筛选答案超时，问题: {question}")
            relevant_indices = []
        
        if not relevant_indices:
            logger.warning(f"AI 认为没有合适的答案或超时，问题: {question}")
            final_index = random.choice(range(len(candidates)))
        else:
            final_index = random.choice(relevant_indices)  # 在 AI 推荐中随机选一个
        
        final_answer = candidates[final_index]
        
        # 使用 language_utils 模块中的函数让AI生成解释
        # 添加超时控制
        try:
            explanation = await asyncio.wait_for(
                generate_answer_explanation(final_answer, question, context.config),
                timeout=30  # 设置30秒超时
            )
            if not explanation:
                explanation = "时机未到，静待花开。"
        except asyncio.TimeoutError:
            logger.warning(f"AI 生成解释超时，问题: {question}")
            explanation = "时机未到，静待花开。"
        
        # 尝试生成答案之书图片
        try:
            logger.info(f"正在为问题 '{question}' 生成答案图片")
            # 添加超时控制
            image_base64 = await asyncio.wait_for(
                generate_answer_book_image_base64(final_answer, explanation),
                timeout=20  # 设置20秒超时
            )
            
            # 构建响应消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_image(f"base64://{image_base64}")
            
            # 发送最终结果
            await builder.send()
        except asyncio.TimeoutError:
            logger.error(f"生成答案图片超时: {question}")
            # 回退到文本响应
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"\n")
            builder.add_text(f"✨ {final_answer}\n——{explanation}")
            
            # 发送最终结果
            await builder.send()
        except Exception as e:
            logger.error(f"生成答案图片时发生错误: {str(e)}")
            # 回退到文本响应
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"\n")
            builder.add_text(f"✨ {final_answer}\n——{explanation}")
            
            # 发送最终结果
            await builder.send()
        
        # 撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)
        
    except Exception as e:
        logger.error(f"处理ask命令时发生错误: {str(e)}")
        # 发送错误消息
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"\n❌ 处理请求时发生错误: {str(e)}")
        
        await error_builder.send()
        
        # 撤回处理中提示消息
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

async def load_answers(filename="assets/text/answerbook.json"):
    """加载答案库，格式: [["english", "中文"], ...]"""
    try:
        async with aiofiles.open(filename, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)
        # 提取中文部分作为可选项
        return [item[1] for item in data if isinstance(item, list) and len(item) >= 2]
    except FileNotFoundError:
        logger.error(f"❌ 错误：找不到文件 '{filename}'")
        raise
    except Exception as e:
        logger.error(f"❌ 加载答案库失败：{str(e)}")
        raise

def get_random_answers(answers_pool, n=5):
    """从题库中随机抽取 n 个答案"""
    return random.sample(answers_pool, min(n, len(answers_pool)))
