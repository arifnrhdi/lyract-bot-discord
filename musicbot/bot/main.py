import logging
from difflib import SequenceMatcher

import discord
from discord.ext import commands

from .config import load_config
from .db import Database
from .intent import IntentParser, fast_path, strip_bot_mention
from .player import GuildPlayer
from .sources import AudioSource
from .tools import validate_tool_call
from .ui import ControlView, TrackSelect, now_embed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("musicbot")


class MusicBot(commands.Bot):
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.db = Database(config.database_path)
        self.parser = IntentParser(config.groq_api_key, config.llm_model)
        self.source = AudioSource()
        self.players: dict[int, GuildPlayer] = {}

    async def setup_hook(self):
        await self.db.initialize()
        if not self.source.check_ffmpeg():
            log.error("FFmpeg tidak ditemukan di PATH atau folder bin project; audio tidak dapat diputar.")
        try:
            import nacl  # noqa: F401
        except ImportError:
            log.error("PyNaCl tidak terpasang; install requirements.txt atau `pip install -U PyNaCl`.")

    async def on_ready(self):
        log.info("logged in as %s", self.user)
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening, name="permintaanmu"))

    def player_for(self, guild):
        if guild.id not in self.players:
            self.players[guild.id] = GuildPlayer(guild, self.source, self.db)
        return self.players[guild.id]

    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith("!"):
            await self.process_commands(message)
            return
        if self.user not in message.mentions:
            return
        text = strip_bot_mention(message.content, self.user.id)
        log.info("message after mention strip: user=%s text=%r", message.author.id, text)
        if not text:
            return await message.reply("Ya? Mau muter apa?", mention_author=False)
        await self.handle_request(message, text)

    async def handle_request(self, message, text):
        try:
            fast = fast_path(text)
            if fast and fast.tool == "status":
                player = self.players.get(message.guild.id)
                voice = player.voice if player else None
                voice_status = "tersambung" if voice and voice.is_connected() else "idle"
                queue_count = len(player.queue) if player else 0
                volume = round(player.volume * 100) if player else 50
                log.info("user=%s tool=status result=ok guild=%s", message.author.id, message.guild.id)
                return await message.reply(
                    f"Bot aktif · latensi {round(self.latency * 1000)} ms · voice {voice_status} · volume {volume}% · antrean {queue_count} lagu.",
                    mention_author=False)
            intent = await self.parser.parse(text, message.author.id)
            log.info("user=%s tool=%s result=called guild=%s", message.author.id, intent.tool, message.guild.id)
            args = validate_tool_call(intent.tool, intent.arguments) if intent.tool not in ("show_queue", "shuffle") else {}
            player = self.player_for(message.guild)
            member_voice = getattr(message.author.voice, "channel", None)
            if intent.tool not in ("chat", "volume", "show_queue") and not member_voice:
                log.info("user=%s tool=%s result=rejected_voice guild=%s", message.author.id, intent.tool, message.guild.id)
                return await message.reply("Masuk voice dulu, baru aku bisa muterin lagu.", mention_author=False)
            if intent.tool == "chat":
                log.info("user=%s tool=chat result=replied guild=%s", message.author.id, message.guild.id)
                return await message.reply(args["reply"], mention_author=False,
                                           allowed_mentions=discord.AllowedMentions.none())
            if intent.tool in ("play", "queue_add", "recommend"):
                queries = ([args["query"]] if intent.tool == "play" else args["queries"]
                           if intent.tool == "queue_add" else ["lagu populer Indonesia"])
                tracks = []
                limit = args["count"] if intent.tool == "recommend" else 3
                for query in queries:
                    found = await self.source.search(query, limit)
                    if not found:
                        continue
                    for track in found[:limit]:
                        track.requester = message.author.display_name
                    if intent.tool == "play" and self._ambiguous(query, found):
                        log.info("user=%s tool=play result=selection guild=%s", message.author.id, message.guild.id)
                        return await message.channel.send(view=TrackSelect(found, player, member_voice))
                    tracks.extend(found[:limit] if intent.tool == "recommend" else found[:1])
                if not tracks:
                    log.info("user=%s tool=%s result=not_found guild=%s", message.author.id, intent.tool, message.guild.id)
                    return await message.reply("Belum ketemu lagunya. Coba sebutin judul atau artisnya lebih spesifik, ya.", mention_author=False)
                was_idle = player.current is None and not player.queue
                queue_position = len(player.queue) + 1
                await player.join(member_voice, message.channel)
                await player.add(tracks)
                log.info("user=%s tool=%s result=queued count=%s guild=%s", message.author.id, intent.tool, len(tracks), message.guild.id)
                titles = ", ".join(f"**{track.title.replace(chr(10), ' ')[:80]}**" for track in tracks[:3])
                if len(tracks) > 3:
                    titles += f" dan {len(tracks) - 3} lagu lainnya"
                if not was_idle:
                    response = (f"Oke, masuk antrean: {titles}." if intent.tool == "queue_add"
                                else f"Sip, {titles} masuk antrean (posisi {queue_position}).")
                    title = "Masuk antrean"
                else:
                    response = f"Siap, aku puterin {titles}."
                    title = "Siap diputar"
                embed = discord.Embed(title=title, description=titles, color=discord.Color.blurple())
                return await message.channel.send(content=response, embed=embed, view=ControlView(player),
                                                  allowed_mentions=discord.AllowedMentions.none())
            if intent.tool == "show_queue":
                log.info("user=%s tool=show_queue result=shown guild=%s", message.author.id, message.guild.id)
                lines = ([f"Lagi diputar: {player.current.title[:70].replace(chr(10), ' ')}"]
                         if player.current else [])
                if player.queue:
                    lines.append(f"**Berikutnya ({len(player.queue)} lagu):**")
                    lines.extend(f"{i}. {track.title[:70].replace(chr(10), ' ')}"
                                 for i, track in enumerate(player.queue, 1))
                elif player.current:
                    lines.append("Belum ada lagu berikutnya di antrean.")
                embed = discord.Embed(title="Antrean", description="\n".join(lines) or "Antrean kosong.",
                                      color=discord.Color.blurple())
                return await message.channel.send(embed=embed)
            if intent.tool == "shuffle":
                if len(player.queue) < 2:
                    return await message.reply("Perlu minimal 2 lagu di antrean untuk diacak.", mention_author=False)
                player.shuffle()
                log.info("user=%s tool=shuffle result=ok count=%s guild=%s",
                         message.author.id, len(player.queue), message.guild.id)
                return await message.reply(f"Urutan {len(player.queue)} lagu di antrean sudah diacak.",
                                           mention_author=False)
            if intent.tool == "skip":
                await player.skip()
            elif intent.tool == "pause":
                await player.pause()
            elif intent.tool == "resume":
                await player.resume()
            elif intent.tool == "stop":
                await player.stop()
            elif intent.tool == "volume":
                player.set_volume(args["level"])
                effect = "buat lagu berikutnya" if player.current is None else ""
                return await message.reply(
                    f"Sip, volume {args['level']}%.", mention_author=False)
            elif intent.tool == "now_playing":
                pass
            elif intent.tool == "history":
                rows = await self.db.recent(message.guild.id, args["limit"])
                embed = discord.Embed(title="🕘 Riwayat", description="\n".join(
                    f"[{title}]({url})" for title, url, _ in rows) or "Belum ada riwayat.",
                    color=discord.Color.blurple())
                log.info("user=%s tool=history result=shown guild=%s", message.author.id, message.guild.id)
                return await message.channel.send(embed=embed)
            else:
                raise ValueError("Tool tidak dikenal")
            log.info("user=%s tool=%s result=ok guild=%s", message.author.id, intent.tool, message.guild.id)
            await message.channel.send(embed=now_embed(player, intent.opening), view=ControlView(player))
        except Exception as exc:
            log.info("user=%s tool=%s result=error error=%s", message.author.id,
                     locals().get("intent", None) and intent.tool, type(exc).__name__)
            if type(exc).__name__ == "RateLimitError":
                reply = "Lagi ramai sebentar; coba lagi dalam beberapa detik, ya."
            elif isinstance(exc, TimeoutError):
                reply = "Permintaan musiknya lambat diproses; coba lagi sebentar lagi."
            elif getattr(exc, "code", None) == 4017 or "4017" in str(exc) or "DAVE" in str(exc).upper():
                reply = "Koneksi voice gagal (DAVE/4017). Upgrade discord.py dan pasang davey dengan `pip install -U discord.py davey`."
            elif "pynacl" in str(exc).lower():
                reply = "Dukungan voice belum terpasang. Pasang PyNaCl dengan `pip install -U PyNaCl`."
            elif "ffmpeg" in str(exc).lower():
                reply = "FFmpeg tidak ditemukan di PATH atau folder bin project. Pasang FFmpeg, lalu mulai ulang bot."
            elif isinstance(exc, ValueError):
                reply = str(exc)
            else:
                reply = "Ada kendala saat memproses permintaan. Coba lagi, ya."
                log.exception("Permintaan musik gagal")
            await message.reply(reply, mention_author=False)

    @staticmethod
    def _ambiguous(query, tracks):
        if len(tracks) < 2:
            return False
        score = lambda title: SequenceMatcher(None, query.casefold(), title.casefold()).ratio()
        ranked = sorted((score(t.title) for t in tracks), reverse=True)
        return ranked[0] < 0.72 or ranked[0] - ranked[1] < 0.12


def create_bot():
    config = load_config()
    bot = MusicBot(config)

    @bot.command(name="setmusic")
    @commands.has_guild_permissions(manage_channels=True)
    async def set_music_channel(ctx):
        await bot.db.set_channel(ctx.guild.id, ctx.channel.id)
        await ctx.reply("Channel dicatat. Untuk permintaan musik, mention bot atau gunakan `!music <permintaan>`.",
                        mention_author=False)

    @set_music_channel.error
    async def set_music_channel_error(ctx, error):
        await ctx.reply("Hanya pengelola channel yang dapat menyetel channel musik.", mention_author=False)

    @bot.command(name="unsetmusic")
    @commands.has_guild_permissions(manage_channels=True)
    async def unset_music_channel(ctx):
        cleared = await bot.db.clear_channel(ctx.guild.id)
        reply = "Pengaturan `!setmusic` dihapus." if cleared else "Belum ada pengaturan `!setmusic`."
        await ctx.reply(reply, mention_author=False)

    @unset_music_channel.error
    async def unset_music_channel_error(ctx, error):
        await ctx.reply("Hanya pengelola channel yang dapat menghapus pengaturan channel musik.",
                        mention_author=False)

    @bot.command(name="music")
    async def music_request(ctx, *, request=""):
        request = request.strip()
        if not request:
            return await ctx.reply("Tulis permintaan setelah `!music`, misalnya `!music puterin lagu santai`.",
                                   mention_author=False)
        await bot.handle_request(ctx.message, request)

    return bot


def main():
    bot = create_bot()
    bot.run(bot.config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
