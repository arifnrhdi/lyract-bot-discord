# Discord Music Bot

Bot musik Discord dengan input natural berbahasa Indonesia. Musik dikontrol dengan mention bot atau prefix `!music`; tidak ada slash command musik. LLM hanya memilih satu tool allowlist, lalu kode bot memvalidasi dan menjalankannya.

## Persiapan

- Python 3.12
- FFmpeg tersedia di `PATH`
- Bot Discord dengan izin Send Messages, Embed Links, Connect, dan Speak
- Aktifkan **Message Content Intent** di Discord Developer Portal
- Groq API key

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Isi `DISCORD_TOKEN` dan `GROQ_API_KEY` di `.env`. `LLM_MODEL` opsional (default `openai/gpt-oss-120b`); `DATABASE_PATH` opsional (default `musicbot.sqlite3`). Jangan commit `.env`.

## Jalankan

```powershell
python -m musicbot.bot.main
```

Kirim `@Bot puterin lagu santai` atau `!music puterin lagu santai` di channel mana pun. Bot mengabaikan pesan biasa yang tidak menyebut bot atau diawali command yang dikenali. Untuk memutar atau mengontrol musik, peminta harus berada di voice channel. Admin dengan izin Manage Channels bisa mencatat channel memakai `!setmusic` dan menghapusnya dengan `!unsetmusic`.

Contoh:

- `puterin lagu galau yang santai`
- `skip bosen`
- `pause dulu`, `lanjut`
- `yang tadi apa sih?`
- `lihat antrean`

Hasil pencarian lagu yang ambigu menampilkan pilihan. Embed kontrol menyediakan tombol jeda, skip, loop, dan stop. Riwayat disimpan lokal di SQLite.

Jalankan tes dengan `pytest`.
