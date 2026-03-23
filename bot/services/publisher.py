from __future__ import annotations
import logging
import re
from html import unescape as html_unescape
from pathlib import Path

from telegram import Bot
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

_FALLBACK_SUFFIX = "\n\n(Sent as file — non-streamable format)"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)

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
    except BadRequest as e:
        logger.warning("send_video failed (BadRequest), falling back to send_document: %s", e)

    plain_caption = html_unescape(_strip_html(caption))
    max_len = 1024 - len(_FALLBACK_SUFFIX)
    fallback_caption = plain_caption[:max_len] + _FALLBACK_SUFFIX
    try:
        msg = await bot.send_document(
            chat_id=channel_chat_id,
            document=video_path,
            caption=fallback_caption,
        )
        return msg.message_id
    except Exception as e:
        logger.error("send_document also failed: %s", e)
        return None
