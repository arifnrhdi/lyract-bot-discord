import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from musicbot.bot.main import MusicBot


def fake_bot():
    user = SimpleNamespace(id=42)
    bot = SimpleNamespace(
        user=user,
        db=SimpleNamespace(get_channel=AsyncMock(return_value=None)),
        parser=SimpleNamespace(parse=AsyncMock(side_effect=AssertionError("LLM dipanggil"))),
        handle_request=None,
        process_commands=AsyncMock(),
        latency=0.012,
        players={},
    )
    bot.handle_request = lambda message, text: MusicBot.handle_request(bot, message, text)
    return bot


def fake_message(content):
    return SimpleNamespace(
        author=SimpleNamespace(bot=False, id=7),
        guild=SimpleNamespace(id=9),
        channel=SimpleNamespace(id=10),
        content=content,
        mentions=[SimpleNamespace(id=42)],
        reply=AsyncMock(),
    )


def test_mention_ping_uses_fast_path_without_llm():
    bot, message = fake_bot(), fake_message("<@42> ping")
    asyncio.run(MusicBot.on_message(bot, message))
    bot.parser.parse.assert_not_awaited()
    assert "Bot aktif" in message.reply.await_args.args[0]
    assert "12 ms" in message.reply.await_args.args[0]


def test_empty_mention_gets_prompt_without_llm():
    bot, message = fake_bot(), fake_message("<@!42>")
    asyncio.run(MusicBot.on_message(bot, message))
    bot.parser.parse.assert_not_awaited()
    assert message.reply.await_args.args[0] == "Iya? Mau diputerin apa? 🎧"
