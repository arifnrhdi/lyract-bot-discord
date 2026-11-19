import asyncio
from types import SimpleNamespace

import pytest

from musicbot.bot.intent import IntentParser, fast_path, strip_bot_mention


@pytest.mark.parametrize("text,tool", [
    ("skip bosen", "skip"), ("pause dulu", "pause"),
    ("lanjut", "resume"), ("stop", "stop"),
    ("yang tadi apa sih?", "now_playing"), ("lihat queue", "show_queue"),
])
def test_fast_path(text, tool):
    assert fast_path(text).tool == tool


@pytest.mark.parametrize("text,tool", [
    ("ping", "status"), ("STATUS", "status"), ("hidup?", "status"),
    ("<@42> skip bosen", "skip"), ("<@!42> pause", "pause"), ("<@42> stop", "stop"),
])
def test_mention_is_removed_before_fast_path(text, tool):
    assert fast_path(strip_bot_mention(text, 42)).tool == tool


def test_unrecognized_uses_llm(monkeypatch):
    parser = IntentParser("test", "model")
    async def fail(*args, **kwargs):
        raise AssertionError("LLM dipanggil")
    monkeypatch.setattr(parser.client.chat.completions, "create", fail)
    assert fast_path("puterin lagu galau") is None


def test_llm_tool_call_is_parsed(monkeypatch):
    parser = IntentParser("test", "model")
    call = SimpleNamespace(function=SimpleNamespace(name="play", arguments='{"query":"lagu santai"}'))
    message = SimpleNamespace(tool_calls=[call], content="Siap, aku putarkan.")
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    async def complete(**kwargs):
        assert kwargs["tool_choice"] == "required"
        return response
    monkeypatch.setattr(parser.client.chat.completions, "create", complete)
    intent = asyncio.run(parser.parse("puterin lagu santai", 123))
    assert intent.tool == "play"
    assert intent.arguments == {"query": "lagu santai"}


def test_rate_limit_applies_to_fast_path():
    parser = IntentParser("test", "model")
    async def check():
        assert (await parser.parse("skip", 99)).tool == "skip"
        with pytest.raises(ValueError, match="Tunggu sebentar"):
            await parser.parse("pause", 99)
    asyncio.run(check())
