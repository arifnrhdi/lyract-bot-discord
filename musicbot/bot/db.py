import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path

    async def initialize(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS guilds (guild_id INTEGER PRIMARY KEY, music_channel_id INTEGER NOT NULL)")
            await db.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            await db.commit()

    async def set_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO guilds VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET music_channel_id=excluded.music_channel_id", (guild_id, channel_id))
            await db.commit()

    async def get_channel(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT music_channel_id FROM guilds WHERE guild_id=?", (guild_id,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else None

    async def clear_channel(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("DELETE FROM guilds WHERE guild_id=?", (guild_id,))
            await db.commit()
            return cur.rowcount > 0

    async def add(self, guild_id: int, track):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO history(guild_id,title,url) VALUES(?,?,?)", (guild_id, track.title, track.webpage_url))
            await db.commit()

    async def recent(self, guild_id: int, limit: int):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT title,url,played_at FROM history WHERE guild_id=? ORDER BY id DESC LIMIT ?", (guild_id, limit)) as cur:
                return await cur.fetchall()
