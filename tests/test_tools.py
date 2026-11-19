import pytest

from musicbot.bot.tools import validate_tool_call


@pytest.mark.parametrize("name,args", [
    ("play", {"query": "lagu santai"}), ("volume", {"level": 0}),
    ("recommend", {"count": 5}), ("history", {"limit": 50}),
    ("queue_add", {"queries": ["lagu"]}),
])
def test_valid_calls(name, args):
    assert validate_tool_call(name, args) == args


@pytest.mark.parametrize("name,args", [
    ("exec", {}), ("volume", {"level": 101}), ("volume", {"level": True}),
    ("recommend", {"count": 6}), ("play", {"query": "  "}),
    ("play", {"query": "lagu", "extra": "arg"}),
])
def test_rejects_invalid_calls(name, args):
    with pytest.raises(ValueError):
        validate_tool_call(name, args)
