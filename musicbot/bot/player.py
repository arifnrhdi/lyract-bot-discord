import asyncio
import logging
import random

from .sources import AudioSource, Track
from .ui import now_embed

log = logging.getLogger(__name__)


class GuildPlayer:
    def __init__(self, guild, source: AudioSource, history):
        self.guild, self.source, self.history = guild, source, history
        self.voice = None
        self.queue: list[Track] = []
        self.current: Track | None = None
        self.volume = 0.5
        self.loop = False
        self.task: asyncio.Task | None = None
        self.idle_task: asyncio.Task | None = None

    async def join(self, channel, text_channel=None):
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
        if text_channel:
            self.text_channel = text_channel
        if self.voice and self.voice.is_connected():
            if self.voice.channel != channel:
                await self.guild.change_voice_state(channel=channel, self_deaf=True)
        else:
            self.voice = await channel.connect(self_deaf=True)
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._play_loop())

    async def add(self, tracks: list[Track]):
        if len(self.queue) + len(tracks) > 50:
            raise ValueError("Antrean maksimal 50 lagu.")
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
        self.queue.extend(tracks)
        if self.voice and self.voice.is_connected() and (not self.task or self.task.done()):
            self.task = asyncio.create_task(self._play_loop())

    def shuffle(self):
        random.shuffle(self.queue)

    async def _play_loop(self):
        while self.voice and self.voice.is_connected():
            if not self.queue:
                self.current = None
                self.idle_task = asyncio.create_task(self._disconnect_when_idle())
                return
            previous = self.current
            self.current = self.queue[0] if self.loop and self.current else self.queue.pop(0)
            track_changed = previous is not None and self.current is not previous
            try:
                source = await self.source.create(self.current, self.volume)
                done = asyncio.get_running_loop().create_future()
                loop = asyncio.get_running_loop()
                def after(error):
                    def finish():
                        if error:
                            log.error("play error: %s", error)
                            asyncio.create_task(self._notify_audio_error(error))
                        if not done.done():
                            done.set_result(error)
                    loop.call_soon_threadsafe(finish)
                self.voice.play(source, after=after)
                if track_changed and getattr(self, "text_channel", None):
                    try:
                        await self.text_channel.send(embed=now_embed(self))
                    except Exception:
                        log.exception("Gagal mengumumkan lagu yang sedang diputar")
                await self.history.add(self.guild.id, self.current)
                await done
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Gagal memutar audio di guild %s", self.guild.id)
                await self._notify_audio_error(exc)
                if self.loop:
                    self.loop = False

    async def _disconnect_when_idle(self):
        await asyncio.sleep(30 * 60)
        voice = self.voice
        if voice and voice.is_connected() and self.current is None and not self.queue:
            try:
                log.info("disconnecting idle voice connection guild=%s", self.guild.id)
                await voice.disconnect()
                if self.voice is voice:
                    self.voice = None
            except Exception:
                log.exception("Gagal keluar dari voice setelah idle guild=%s", self.guild.id)

    async def _notify_audio_error(self, error):
        if not getattr(self, "text_channel", None):
            return
        detail = str(error).lower()
        if "ffmpeg" in detail:
            message = "FFmpeg tidak ditemukan di PATH atau folder bin project. Pasang FFmpeg, lalu mulai ulang bot."
        elif getattr(error, "code", None) == 4017 or "4017" in detail or "dave" in detail:
            message = "Koneksi voice gagal (DAVE/4017). Upgrade discord.py dan pasang davey dengan `pip install -U discord.py davey`."
        elif "pynacl" in detail:
            message = "Dukungan voice belum terpasang. Pasang PyNaCl dengan `pip install -U PyNaCl`."
        else:
            message = "Audio gagal diputar. Coba lagi; detail sudah dicatat di log bot."
        try:
            await self.text_channel.send(message)
        except Exception:
            log.exception("Gagal mengirim pesan error audio ke channel")

    async def skip(self):
        self.loop = False
        if self.voice and self.voice.is_playing():
            self.voice.stop()
        elif self.queue:
            self.queue.pop(0)

    async def pause(self):
        if self.voice and self.voice.is_playing():
            self.voice.pause()

    async def resume(self):
        if self.voice and self.voice.is_paused():
            self.voice.resume()

    async def stop(self):
        self.queue.clear()
        self.loop = False
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
        if self.voice:
            self.voice.stop()
            await self.voice.disconnect()
            self.voice = None
        self.current = None

    def set_volume(self, level: int):
        self.volume = level / 100
        if self.voice and self.voice.source:
            self.voice.source.volume = self.volume

    def close(self):
        if self.task:
            self.task.cancel()
        if self.idle_task:
            self.idle_task.cancel()

