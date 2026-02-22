# 处理音乐搜索和播放命令

import asyncio
import json
import os
import concurrent.futures
from utils.audio_utils import download_audio_file, safe_remove_file, clean_temp_files
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from utils.music.netease_xmsjorg import search_songs as netease_search_songs
from utils.music.gequbao import search_songs as gequbao_search_songs
from utils.music.qq_xmsjorg import search_songs as qq_search_songs
from utils.api_utils import call_onebot_api
from utils.task_utils import create_monitored_task

logger = get_logger("MusicCommand")

# 存储用户的搜索关键词（用于平台选择后使用）
user_search_keywords = {}  # key: f"{group_id}_{user_id}", value: keyword

# 存储搜索结果（用于选择歌曲）
search_results_cache = {}  # key: f"{group_id}_{user_id}", value: { "songs": [...], "platform": "netease" }



async def handle_music_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> CommandResponse:
    """
    支持的用法：
    - /music <歌名>                     → 显示平台选择
    - /music <平台代码>                 → 使用上一次关键词在该平台搜索（需先有关键词）
    - /music <平台代码> <歌名>          → 直接在该平台搜索
    - /music <数字编号>                 → 播放最近一次搜索结果中的歌曲
    """
    try:
        if not args:
            return CommandResponse.text("❌ 请提供歌名、平台代码或歌曲编号")

        first_arg = args[0].lower()
        cache_key = f"{group_id}_{user_id}"

        # 情况1: /music <数字编号>
        if first_arg.isdigit():
            song_index = int(first_arg) - 1
            if cache_key not in search_results_cache:
                return CommandResponse.text("❌ 请先搜索歌曲")
            result = search_results_cache[cache_key]
            songs = result["songs"]
            if song_index < 0 or song_index >= len(songs):
                return CommandResponse.text("❌ 歌曲编号无效")
            
            # 发送处理中提示并保存消息ID
            processing_builder = MessageBuilder(context)
            processing_builder.set_group_id(group_id)
            processing_builder.set_user_id(user_id)
            processing_builder.add_at()
            processing_builder.add_text("🎵 正在为您准备歌曲，请稍候...")
            
            async def processing_callback(message_id: str):
                if message_id:
                    # 启动后台任务处理歌曲播放，并传递处理中消息的ID
                    create_monitored_task(
                        play_selected_song(context, user_id, group_id, songs[song_index], result["platform"], message_id),
                        name=f"MusicCommand_play_{user_id}_{group_id}"
                    )
            
            processing_builder.set_callback(processing_callback)
            
            # 发送处理中提示
            await processing_builder.send()
            
            # 返回none表示已经通过builder发送了消息
            return CommandResponse.none()

        # 情况2: /music <平台代码>
        if len(args) == 1 and first_arg in ['n', 'g', 'q']:
            if cache_key not in user_search_keywords:
                return CommandResponse.text("❌ 请先使用 `/music <歌名>` 搜索歌曲")
            keyword = user_search_keywords[cache_key]
            platform = {'n': 'netease', 'g': 'gequbao', 'q': 'qq'}[first_arg]
            
            # 发送处理中提示并保存消息ID
            processing_builder = MessageBuilder(context)
            processing_builder.set_group_id(group_id)
            processing_builder.set_user_id(user_id)
            processing_builder.add_at()
            processing_builder.add_text("🔍 正在搜索歌曲，请稍候...")
            
            async def processing_callback(message_id: str):
                if message_id:
                    # 启动后台任务处理搜索，并传递处理中消息的ID
                    create_monitored_task(
                        do_search(context, user_id, group_id, keyword, platform, message_id),
                        name=f"MusicCommand_search_{user_id}_{group_id}"
                    )
            
            processing_builder.set_callback(processing_callback)
            
            # 发送处理中提示
            await processing_builder.send()
            
            # 返回none表示已经通过builder发送了消息
            return CommandResponse.none()

        # 情况3: /music <平台代码> <歌名>
        if len(args) >= 2 and first_arg in ['n', 'g', 'q']:
            keyword = ' '.join(args[1:])
            platform = {'n': 'netease', 'g': 'gequbao', 'q': 'qq'}[first_arg]
            
            # 发送处理中提示并保存消息ID
            processing_builder = MessageBuilder(context)
            processing_builder.set_group_id(group_id)
            processing_builder.set_user_id(user_id)
            processing_builder.add_at()
            processing_builder.add_text("🔍 正在搜索歌曲，请稍候...")
            
            async def processing_callback(message_id: str):
                if message_id:
                    # 启动后台任务处理搜索，并传递处理中消息的ID
                    create_monitored_task(
                        do_search(context, user_id, group_id, keyword, platform, message_id),
                        name=f"MusicCommand_search_{user_id}_{group_id}"
                    )
            
            processing_builder.set_callback(processing_callback)
            
            # 发送处理中提示
            await processing_builder.send()
            
            # 返回none表示已经通过builder发送了消息
            return CommandResponse.none()

        # 情况4: /music <歌名>
        keyword = ' '.join(args)
        
        # 发送处理中提示并保存消息ID
        processing_builder = MessageBuilder(context)
        processing_builder.set_group_id(group_id)
        processing_builder.set_user_id(user_id)
        processing_builder.add_at()
        processing_builder.add_text("🎵 正在处理您的请求，请稍候...")
        
        async def processing_callback(message_id: str):
            if message_id:
                # 启动后台任务处理平台选择提示，并传递处理中消息的ID
                create_monitored_task(
                    prompt_platform_choice(context, user_id, group_id, keyword, message_id),
                    name=f"MusicCommand_prompt_{user_id}_{group_id}"
                )
        
        processing_builder.set_callback(processing_callback)
        
        # 发送处理中提示
        await processing_builder.send()
        
        # 返回none表示已经通过builder发送了消息
        return CommandResponse.none()

    except Exception as e:
        logger.error(f"处理音乐命令异常: {e}")
        return CommandResponse.text(f"❌ 处理音乐命令失败: {str(e)}")

async def prompt_platform_choice(context: BotContext, user_id: str, group_id: str, keyword: str, processing_message_id: str) -> None:
    """提示用户选择平台"""
    cache_key = f"{group_id}_{user_id}"
    user_search_keywords[cache_key] = keyword

    builder = MessageBuilder(context)
    builder.set_group_id(group_id)
    builder.set_user_id(user_id)
    builder.add_at()
    builder.add_text(f"\n🎵 搜索歌曲：{keyword}\n")
    builder.add_text("请选择音乐平台：\n")
    builder.add_text("• /music n — 网易云音乐\n")
    builder.add_text("• /music g — Gequbao免费音乐\n")
    builder.add_text("• /music q — QQ音乐\n")
    builder.add_text("\n20秒后自动撤回")
    builder.set_auto_recall(20)  # 设置20秒后自动撤回

    await builder.send()
    
    # 撤回处理中提示消息
    await try_recall_processing_message(context, processing_message_id)

async def do_search(context: BotContext, user_id: str, group_id: str, keyword: str, platform: str, processing_message_id: str) -> None:
    """执行搜索"""
    cache_key = f"{group_id}_{user_id}"
    platform_names = {
        'netease': '网易云音乐',
        'gequbao': 'Gequbao免费音乐',
        'qq': 'QQ音乐'
    }
    platform_name = platform_names.get(platform, platform)

    

    # 发送搜索状态
    status_builder = MessageBuilder(context)
    status_builder.set_group_id(group_id)
    status_builder.set_user_id(user_id)
    status_builder.add_at()
    status_builder.add_text(f"\n🔍 正在{platform_name}搜索 '{keyword}'，请稍候...")
    status_builder.set_auto_recall(20)  # 设置20秒后自动撤回
    await status_builder.send()
    
    # 撤回处理中提示消息
    await try_recall_processing_message(context, processing_message_id)

    try:
        loop = asyncio.get_event_loop()
        if platform == 'netease':
            result = await loop.run_in_executor(None, netease_search_songs, keyword)
        elif platform == 'gequbao':
            result = await loop.run_in_executor(None, gequbao_search_songs, keyword)
        else:
            result = await loop.run_in_executor(None, qq_search_songs, keyword)

        if not result.get('success'):
            error_builder = MessageBuilder(context)
            error_builder.set_group_id(group_id)
            error_builder.set_user_id(user_id)
            error_builder.add_at()
            error_builder.add_text(f"\n❌ {platform_name}搜索失败: {result.get('error', '未知错误')}")
            await error_builder.send()
            
            # 撤回处理中提示消息
            await try_recall_processing_message(context, processing_message_id)
            return

        songs = result.get('songs', [])
        if not songs:
            error_builder = MessageBuilder(context)
            error_builder.set_group_id(group_id)
            error_builder.set_user_id(user_id)
            error_builder.add_at()
            error_builder.add_text(f"\n❌ {platform_name}未找到相关歌曲")
            await error_builder.send()
            
            # 撤回处理中提示消息
            await try_recall_processing_message(context, processing_message_id)
            return

        # 缓存结果（覆盖之前的）
        search_results_cache[cache_key] = {
            "songs": songs[:10],  # 最多缓存10首
            "platform": platform
        }

        # 构建结果消息
        res_builder = MessageBuilder(context)
        res_builder.set_group_id(group_id)
        res_builder.set_user_id(user_id)
        res_builder.add_at()
        res_builder.add_text(f"\n🎵 {platform_name}搜索结果：\n")
        for i, song in enumerate(songs[:10]):
            vip = "💎 VIP" if song.get('vip_tag') else ""
            res_builder.add_text(f"{i+1}. {song['title']} - {song['author']} {vip}\n")
        res_builder.add_text("\n发送 /music <编号> 播放歌曲（20秒后撤回）")
        res_builder.set_auto_recall(20)  # 设置20秒后自动撤回
        await res_builder.send()
        
        # 撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)

    except Exception as e:
        logger.error(f"搜索异常: {e}")
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"\n❌ 搜索失败: {str(e)}")
        await error_builder.send()
        
        # 撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)
    finally:
        # 状态消息已通过 set_auto_recall 自动撤回
        pass

async def play_selected_song(context: BotContext, user_id: str, group_id: str, song_info: dict, platform: str, processing_message_id: str) -> None:
    """播放选中的歌曲"""
    try:
        # 撤回处理中提示消息
        await try_recall_processing_message(context, processing_message_id)
        
        cache_key = f"{group_id}_{user_id}"
        platform_names = {
            'netease': '网易云音乐',
            'gequbao': 'Gequbao免费音乐',
            'qq': 'QQ音乐'
        }
        platform_name = platform_names.get(platform, platform)

        if song_info.get('vip_tag'):
            error_builder = MessageBuilder(context)
            error_builder.set_group_id(group_id)
            error_builder.set_user_id(user_id)
            error_builder.add_at()
            error_builder.add_text(f"\n❌ {platform_name}: {song_info['title']} - {song_info['author']} 是VIP歌曲，无法播放")
            await error_builder.send()
            return

        song_url = song_info.get('url')
        if not song_url:
            error_builder = MessageBuilder(context)
            error_builder.set_group_id(group_id)
            error_builder.set_user_id(user_id)
            error_builder.add_at()
            error_builder.add_text(f"\n❌ {platform_name}: {song_info['title']} - {song_info['author']} 无可用链接")
            await error_builder.send()
            return

        logger.info(f"用户 {user_id} 点播 {platform_name}: {song_info['title']} - {song_info['author']}")

        try:
            song_filename = f"{song_info['title']} - {song_info['author']}.mp3"
            local_path = await download_audio_file(song_url, song_filename, platform)

            if local_path and os.path.exists(local_path):
                # 先尝试发送语音消息
                file_url = f"file:///{os.path.abspath(local_path).replace(os.sep, '/')}"
                voice_result = await call_onebot_api(
                    context=context,
                    action="send_group_msg",
                    params={
                        "group_id": int(group_id),
                        "message": [
                            {
                                "type": "record",
                                "data": {
                                    "file": file_url
                                }
                            }
                        ]
                    }
                )
                
                # 检查语音消息是否发送成功
                voice_success = (voice_result and voice_result.get("success") and 
                               voice_result.get("data", {}).get("status") == "ok")
                
                if voice_success:
                    logger.info("语音消息发送成功")
                else:
                    logger.warning("语音消息发送失败，尝试上传文件")
                    # 语音发送失败，尝试上传文件到群文件
                    upload_result = await call_onebot_api(
                        context=context,
                        action="upload_group_file",
                        params={
                            "group_id": int(group_id),
                            "file": local_path,
                            "name": song_filename,
                            "folder": "/"
                        }
                    )
                    
                    # 检查文件上传是否成功
                    upload_success = (upload_result and upload_result.get("success") and 
                                    upload_result.get("data", {}).get("status") == "ok")
                    
                    if upload_success:
                        logger.info("歌曲文件上传成功")
                    else:
                        logger.warning("歌曲文件上传失败")

                # 发送文本消息
                success_builder = MessageBuilder(context)
                success_builder.set_group_id(group_id)
                success_builder.set_user_id(user_id)
                success_builder.add_at()
                
                if voice_success:
                    success_builder.add_text(f"\n✅ 已发送语音：{song_info['title']} - {song_info['author']}")
                else:
                    # 不显示烦人的报错提示，只显示成功信息
                    success_builder.add_text(f"\n✅ 已上传歌曲：{song_info['title']} - {song_info['author']}")
                    
                await success_builder.send()
            else:
                await send_fallback_link(context, user_id, group_id, song_info, platform_name, song_url)

        except Exception as e:
            logger.error(f"播放歌曲时发生错误: {e}")
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"\n❌ 播放歌曲时发生错误: {str(e)}")
            await builder.send()
    finally:
        if 'local_path' in locals() and local_path:
            await safe_remove_file(local_path)
        # 清理缓存
        search_results_cache.pop(cache_key, None)
        user_search_keywords.pop(cache_key, None)
        # 后台清理旧文件
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, clean_temp_files, 24)

    return CommandResponse.none()

async def send_fallback_link(context, user_id, group_id, song, platform_name, url):
    builder = MessageBuilder(context)
    builder.set_group_id(group_id)
    builder.set_user_id(user_id)
    builder.add_at()
    builder.add_text(f"\n🎶 {platform_name}为您找到：{song['title']} - {song['author']}")
    builder.add_text(f"\n🔗 直链：{url}")
    builder.add_text("\n点击可播放或下载")
    await builder.send()

async def safe_recall_message(context, message_id):
    try:
        result = await call_onebot_api(context, "delete_msg", {"message_id": message_id})
        if result and result.get("success"):
            logger.debug(f"成功撤回消息 {message_id}")
        else:
            logger.warning(f"撤回消息失败: {result}")
    except Exception as e:
        logger.warning(f"撤回消息异常: {e}")

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