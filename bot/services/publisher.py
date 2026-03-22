from __future__ import annotations
import logging
from pathlib import Path
from telegram import Bot

logger = logging.getLogger(__name__)

_FALLBACK_SUFFIX = "\n\n<i>(Sent as file — non-streamable format)</i>"

async def publish_video(
    bot: Bot,
    *,
    channel_chat_id: int,
    file_path: str,
    caption: str,
    duration: int | None = None,
    width: int | None = None,
    height: int | None = None,
) -> int | None:
    video_path = Path(file_path)
    try:
        msg = await bot.send_video(
            chat_id=channel_chat_id,
            video=video_path,
            caption=caption,
            parse_mode="HTML",
            supports_streaming=True,
            duration=duration,
            width=width,
            height=height,
        )
        return msg.message_id
    except Exception as e:
        logger.warning("send_video failed, falling back to send_document: %s", e)

    max_caption_len = 1024 - len(_FALLBACK_SUFFIX)
    fallback_caption = caption[:max_caption_len] + _FALLBACK_SUFFIX
    try:
        msg = await bot.send_document(
            chat_id=channel_chat_id,
            document=video_path,
            caption=fallback_caption,
            parse_mode="HTML",
        )
        return msg.message_id
    except Exception as e:
        logger.error("send_document also failed: %s", e)
        return None
