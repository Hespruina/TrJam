# 处理 '/rua' 命令

from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_utils import parse_at_or_qq
from PIL import Image, ImageDraw
import requests
import os
import base64
from io import BytesIO
from utils.message_sender import MessageBuilder

logger = get_logger("RuaCommand")

# 获取当前脚本目录
script_dir = os.path.dirname(os.path.abspath(__file__))
# 资源目录改为 assets/image/rua
RUa_ASSETS_DIR = os.path.join(script_dir, "..", "assets", "image", "rua")

# make_rua_gif_base64函数实现
def make_rua_gif_base64(input_image, data_dir=RUa_ASSETS_DIR, speed_factor=1):
    """
    传入一张图片（路径或 PIL Image），返回 rua 动图的 base64 字符串。

    :param input_image: 图片路径（str）或 PIL.Image.Image 对象
    :param data_dir: 素材目录，默认为当前脚本下的 'data' 文件夹
    :param speed_factor: 速度因子，默认为1（正常速度），小于1表示慢速，大于1表示快速
    :return: base64 编码的 GIF 字符串（str）
    """
    # 加载原始图像
    if isinstance(input_image, str):
        author = Image.open(input_image).convert("RGBA")
    elif isinstance(input_image, Image.Image):
        author = input_image.convert("RGBA")
    else:
        raise ValueError("input_image 必须是文件路径（str）或 PIL.Image.Image 对象")

    # 获取素材列表（按文件名排序以保证顺序）
    try:
        png_files = sorted([
            os.path.join(data_dir, f)
            for f in os.listdir(data_dir)
            if f.lower().endswith('.png')
        ])
        if len(png_files) < 10:
            raise FileNotFoundError(f"素材不足，需要至少10个PNG文件，当前只有 {len(png_files)} 个")
    except Exception as e:
        raise FileNotFoundError(f"无法读取素材目录 {data_dir}: {e}")

    # 预定义参数 jd: [width, height, offset_y, png_path]
    jd = [
        [90, 90, 5, png_files[0]],
        [90, 87, 5, png_files[2]],
        [90, 84, 10, png_files[3]],
        [90, 81, 8, png_files[4]],
        [90, 78, 5, png_files[5]],
        [90, 75, 5, png_files[6]],
        [90, 72, 8, png_files[7]],
        [90, 74, 8, png_files[8]],
        [90, 77, 9, png_files[9]],
        [90, 80, 8, png_files[1]],
    ]

    # 裁剪并加圆形遮罩
    author_resized = author.resize((90, 90))
    alpha_layer = Image.new('L', (90, 90), 0)
    draw = ImageDraw.Draw(alpha_layer)
    draw.ellipse((0, 0, 90, 90), fill=255)
    author_resized.putalpha(alpha_layer)

    gifs = []
    for params in jd:
        w, h, offset, png_path = params
        # 调整 author 高度（h - offset）
        author_frame = author_resized.resize((w, h - offset))

        # 加载素材
        overlay = Image.open(png_path).convert("RGBA")

        # 创建 110x110 画布
        frame = Image.new('RGBA', (110, 110), (255, 255, 255, 255))

        # 粘贴头像（右下对齐）
        x_author = 110 - w
        y_author = 110 - h + offset
        frame.paste(author_frame, (x_author, y_author), author_frame)

        # 粘贴手部素材
        x_hand = 0
        y_hand = 110 - h - offset
        frame.paste(overlay, (x_hand, y_hand), overlay)

        gifs.append(frame)
        overlay.close()

    # 保存为内存中的 GIF
    buffer = BytesIO()
    # 计算帧持续时间，默认35ms
    # 彻底重写计算公式，确保speed_factor越大，速度越快
    # 新公式：基础时间(35ms) / speed_factor，让speed_factor直接决定速度倍率
    # 例如：speed_factor=2 → 17.5ms/帧（约2倍速）
    #      speed_factor=5 → 7ms/帧（约5倍速）
    #      speed_factor=10 → 3.5ms/帧（约10倍速，但受限于最小5ms）
    frame_duration = max(5, int(35 / speed_factor))
    # 记录实际计算的帧持续时间，用于调试
    print(f"Speed factor: {speed_factor}, Frame duration: {frame_duration}ms")
    gifs[0].save(
        buffer,
        format='GIF',
        save_all=True,
        append_images=gifs[1:],
        duration=frame_duration,
        loop=0
    )

    # 转为 base64
    gif_bytes = buffer.getvalue()
    base64_str = base64.b64encode(gif_bytes).decode('utf-8')
    
    # 清理
    buffer.close()
    author_resized.close()
    for img in gifs:
        img.close()

    return base64_str

async def handle_rua_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> str:
    """处理 '/rua' 命令，生成摸头动图。"""
    try:
        # 解析参数中的QQ号或@
        target_qq, remaining_args = parse_at_or_qq(args)
        if not target_qq:
            # 如果没有指定目标，则默认为命令发送者
            target_qq = user_id
            
        logger.info(f"用户 {user_id} 在群 {group_id} 执行了 rua 命令，目标QQ: {target_qq}")
        
        # 获取目标头像
        ava_url = f"http://q2.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=640"
        logger.debug(f"获取头像URL: {ava_url}")
        
        # 下载头像
        response = requests.get(ava_url)
        response.raise_for_status()
        
        # 打开头像图片
        avatar_image = Image.open(BytesIO(response.content))
        
        # 生成摸头动图base64（使用默认速度）
        rua_gif_base64 = make_rua_gif_base64(avatar_image)
        
        # 构建回复消息 - 使用MessageBuilder
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_image(f"base64://{rua_gif_base64}")
        await builder.send()
        logger.info(f"已成功发送摸头动图到群 {group_id}")
        return None  # 返回None，避免重复发送
        
    except requests.RequestException as e:
        logger.error(f"获取头像失败: {e}")
        return "获取头像失败啦，请稍后再试~"
    except Exception as e:
        logger.error(f"处理rua命令时发生异常: {e}", exc_info=True)
        return "生成摸头动图失败啦，请稍后再试~"