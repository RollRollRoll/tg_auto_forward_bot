from __future__ import annotations
import asyncio
import os
import shutil
import tempfile
import time
from pathlib import Path

import yt_dlp

from bot.config import DOWNLOAD_DIR


class DownloadSlotManager:
    def __init__(self):
        self._active_downloads: int = 0
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return self._active_downloads

    async def try_acquire_slot(self, max_slots: int) -> bool:
        async with self._lock:
            if self._active_downloads >= max_slots:
                return False
            self._active_downloads += 1
            return True

    async def release_slot(self) -> None:
        async with self._lock:
            self._active_downloads = max(0, self._active_downloads - 1)


def check_disk_space(max_concurrent: int, max_file_size_mb: int) -> tuple[bool, int]:
    usage = shutil.disk_usage(DOWNLOAD_DIR)
    free_mb = usage.free // (1024 * 1024)
    required_mb = max_concurrent * max_file_size_mb * 2
    return free_mb >= required_mb, free_mb


def cleanup_stale_files(max_age_seconds: int = 3600) -> int:
    download_path = Path(DOWNLOAD_DIR)
    if not download_path.exists():
        return 0
    removed = 0
    now = time.time()
    for item in download_path.iterdir():
        if (now - item.stat().st_mtime) > max_age_seconds:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            removed += 1
    return removed


async def download_video(url: str, *, max_resolution: int = 1080) -> dict:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(dir=DOWNLOAD_DIR)
    os.chmod(tmp_dir, 0o755)

    ydl_opts = {
        "format": (
            f"best[vcodec^=avc][acodec^=mp4a][height<={max_resolution}]"
            f"/bestvideo[vcodec^=avc][height<={max_resolution}]+bestaudio[acodec^=mp4a]"
            f"/bestvideo[vcodec^=avc][height<={max_resolution}]+bestaudio"
            f"/best[height<={max_resolution}]"
            f"/bestvideo[height<={max_resolution}]+bestaudio"
            f"/best"
        ),
        "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
        ],
        "postprocessor_args": {
            "ffmpeg": ["-movflags", "+faststart"],
        },
        "quiet": True,
        "no_warnings": True,
    }

    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, _do_download, ydl_opts, url)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Download failed: {e}") from e

    files = list(Path(tmp_dir).glob("*"))
    if not files:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError("Download produced no files")

    file_path = files[0]
    return {
        "file_path": str(file_path),
        "tmp_dir": tmp_dir,
        "duration": info.get("duration"),
        "width": info.get("width"),
        "height": info.get("height"),
        "title": info.get("title", ""),
        "file_size_mb": file_path.stat().st_size / (1024 * 1024),
    }


def _do_download(ydl_opts: dict, url: str) -> dict:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info or {}
