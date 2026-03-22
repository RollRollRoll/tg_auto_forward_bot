from __future__ import annotations
import logging
import shutil

from telegram import Bot

from bot.database.connection import get_db
from bot.database.crud import create_post_log, get_setting, update_post_log_status
from bot.services.downloader import DownloadSlotManager, check_disk_space, download_video
from bot.services.publisher import publish_video

logger = logging.getLogger(__name__)


async def download_and_publish(
    *, bot: Bot, slot_manager: DownloadSlotManager, user_chat_id: int,
    user_id: int, source_url: str, caption: str, channel_chat_id: int,
) -> None:
    db = await get_db()
    max_concurrent = int(await get_setting(db, "max_concurrent_downloads") or "2")
    max_file_size = int(await get_setting(db, "max_file_size_mb") or "2000")
    max_resolution = int(await get_setting(db, "max_resolution") or "1080")

    if not await slot_manager.try_acquire_slot(max_concurrent):
        active = slot_manager.active_count
        await bot.send_message(
            chat_id=user_chat_id,
            text=f"Server busy ({active}/{max_concurrent} download slots in use). Please resend your link to try again.",
        )
        return

    log_id = None
    tmp_dir = None
    try:
        has_space, free_mb = check_disk_space(max_concurrent, max_file_size)
        if not has_space:
            await bot.send_message(chat_id=user_chat_id, text="Insufficient disk space, please try again later.")
            return

        log_id = await create_post_log(
            db, admin_user_id=user_id, source_url=source_url,
            channel_chat_id=channel_chat_id, caption=caption,
        )

        result = await download_video(source_url, max_resolution=max_resolution)
        tmp_dir = result["tmp_dir"]

        if result["file_size_mb"] > max_file_size:
            await update_post_log_status(db, log_id, status="failed", error_message=f"File too large: {result['file_size_mb']:.1f} MB")
            await bot.send_message(chat_id=user_chat_id, text=f"Video too large ({result['file_size_mb']:.1f} MB), exceeds limit ({max_file_size} MB).")
            return

        await update_post_log_status(db, log_id, status="publishing")
        message_id = await publish_video(
            bot, channel_chat_id=channel_chat_id, file_path=result["file_path"],
            caption=caption, duration=result.get("duration"), width=result.get("width"), height=result.get("height"),
        )

        if message_id:
            await update_post_log_status(db, log_id, status="done", message_id=message_id)
            await bot.send_message(chat_id=user_chat_id, text=f"Published successfully! (message #{message_id})")
        else:
            await update_post_log_status(db, log_id, status="failed", error_message="Failed to send to channel")
            await bot.send_message(chat_id=user_chat_id, text="Send failed, please check Bot permissions.")

    except Exception as e:
        logger.exception("Pipeline error for %s", source_url)
        if log_id:
            await update_post_log_status(db, log_id, status="failed", error_message=str(e))
        await bot.send_message(chat_id=user_chat_id, text=f"Download failed: {e}")
    finally:
        await slot_manager.release_slot()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
