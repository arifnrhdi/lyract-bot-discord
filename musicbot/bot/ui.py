import discord

from .sources import Track


def duration_text(seconds):
    if seconds is None:
        return "—"
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def now_embed(player, opening=""):
    track = player.current or (player.queue[0] if player.queue else None)
    embed = discord.Embed(title="Sedang diputar" if player.current else "Antrean musik",
                          description=opening or (f"[{track.title}]({track.webpage_url})" if track else "Belum ada lagu."),
                          color=discord.Color.blurple())
    if track:
        embed.add_field(name="Durasi", value=duration_text(track.duration))
        embed.add_field(name="Peminta", value=track.requester or "—")
        embed.add_field(name="Posisi", value="Sedang diputar" if player.current else "1")
        if player.queue:
            embed.add_field(name="Antrean", value=f"{len(player.queue)} lagu")
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
    return embed


class TrackSelect(discord.ui.View):
    def __init__(self, tracks: list[Track], player, voice_channel):
        super().__init__(timeout=60)
        self.tracks, self.player, self.voice_channel = tracks[:3], player, voice_channel
        options = [discord.SelectOption(label=t.title[:100], description=duration_text(t.duration), value=str(i))
                   for i, t in enumerate(self.tracks)]
        select = discord.ui.Select(placeholder="Pilih lagu yang dimaksud", options=options)
        select.callback = self.choose
        self.add_item(select)

    async def choose(self, interaction: discord.Interaction):
        if not interaction.user.voice or interaction.user.voice.channel != self.voice_channel:
            return await interaction.response.send_message("Masuk ke voice channel yang sama dulu.", ephemeral=True)
        track = self.tracks[int(interaction.data["values"][0])]
        track.requester = interaction.user.display_name
        was_idle = self.player.current is None and not self.player.queue
        queue_position = len(self.player.queue) + 1
        await self.player.join(self.voice_channel, interaction.channel)
        await self.player.add([track])
        embed = discord.Embed(
            title="Siap diputar" if was_idle else "Masuk antrean",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Durasi", value=duration_text(track.duration))
        if not was_idle:
            embed.add_field(name="Posisi antrean", value=str(queue_position))
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class ControlView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=900)
        self.player = player

    async def control(self, interaction, action):
        member = interaction.user
        if not member.voice or not self.player.voice or member.voice.channel != self.player.voice.channel:
            return await interaction.response.send_message("Masuk ke voice channel bot dulu.", ephemeral=True)
        if action == "pause":
            await self.player.pause()
        elif action == "skip":
            await self.player.skip()
        elif action == "loop":
            self.player.loop = not self.player.loop
        elif action == "shuffle":
            if len(self.player.queue) < 2:
                return await interaction.response.send_message(
                    "Perlu minimal 2 lagu di antrean untuk diacak.", ephemeral=True)
            self.player.shuffle()
            return await interaction.response.send_message("Urutan antrean sudah diacak.", ephemeral=True)
        elif action == "stop":
            await self.player.stop()
        await interaction.response.edit_message(embed=now_embed(self.player), view=self)

    @discord.ui.button(label="Jeda", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction, button):
        await self.control(interaction, "pause")

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction, button):
        await self.control(interaction, "skip")

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary)
    async def loop_button(self, interaction, button):
        await self.control(interaction, "loop")

    @discord.ui.button(label="Acak", style=discord.ButtonStyle.secondary)
    async def shuffle_button(self, interaction, button):
        await self.control(interaction, "shuffle")

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction, button):
        await self.control(interaction, "stop")

