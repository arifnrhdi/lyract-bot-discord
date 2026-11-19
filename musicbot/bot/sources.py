import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

log = logging.getLogger(__name__)


@dataclass
class Track:
    title: str
    webpage_url: str
    duration: int | None = None
    thumbnail: str | None = None
    requester: str = ""


class AudioSource:
    def __init__(self):
        self.options = {"quiet": True, "no_warnings": True, "noplaylist": True,
                        "default_search": "ytsearch3", "format": "bestaudio/best"}
        self.ffmpeg_path = None

    def check_ffmpeg(self):
        self.ffmpeg_path = shutil.which("ffmpeg")
        if not self.ffmpeg_path:
            local_ffmpeg = Path(__file__).resolve().parents[2] / "bin" / "ffmpeg.exe"
            if local_ffmpeg.is_file():
                self.ffmpeg_path = str(local_ffmpeg)
        return self.ffmpeg_path

    def _search(self, query: str, limit: int) -> list[Track]:
        with yt_dlp.YoutubeDL(self.options) as ydl:
            data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        return [Track(e["title"], e.get("webpage_url") or e["url"],
                      e.get("duration"), e.get("thumbnail"))
                for e in data.get("entries", []) if e]

    async def search(self, query: str, limit: int = 3) -> list[Track]:
        return await asyncio.to_thread(self._search, query, limit)

    def _resolve(self, track: Track) -> str:
        with yt_dlp.YoutubeDL(self.options) as ydl:
            data = ydl.extract_info(track.webpage_url, download=False)
        url = data.get("url")
        if not url:
            raise ValueError("Stream audio tidak ditemukan untuk lagu ini.")
        log.info("yt-dlp stream URL: %s", url.split("?", 1)[0])
        return url

    async def create(self, track: Track, volume: float):
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg tidak ditemukan di PATH atau folder bin project.")
        url = await asyncio.to_thread(self._resolve, track)
        import discord
        source = discord.FFmpegPCMAudio(
            url,
            executable=self.ffmpeg_path,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
        )
        return discord.PCMVolumeTransformer(source, volume=volume)

