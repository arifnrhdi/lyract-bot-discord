import json
from typing import Any


TOOL_DEFS = [
    ("play", {"query": {"type": "string"}}, ["query"]),
    ("queue_add", {"queries": {"type": "array", "items": {"type": "string"}, "maxItems": 50}}, ["queries"]),
    ("skip", {}, []), ("pause", {}, []), ("resume", {}, []), ("stop", {}, []),
    ("volume", {"level": {"type": "integer"}}, ["level"]),
    ("now_playing", {}, []),
    ("recommend", {"count": {"type": "integer"}}, ["count"]),
    ("history", {"limit": {"type": "integer"}}, ["limit"]),
    ("chat", {"reply": {"type": "string"}}, ["reply"]),
]

TOOLS = [{"type": "function", "function": {
    "name": name,
    "description": f"Permintaan musik: {name}",
    "parameters": {"type": "object", "properties": props,
                    "required": required, "additionalProperties": False},
}} for name, props, required in TOOL_DEFS]

_ARGS = {name: (set(props), set(required)) for name, props, required in TOOL_DEFS}


def validate_tool_call(name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    if name not in _ARGS:
        raise ValueError("Tool tidak diizinkan")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Argumen tool bukan JSON valid") from exc
    if not isinstance(arguments, dict):
        raise ValueError("Argumen tool harus berupa objek")
    allowed, required = _ARGS[name]
    if set(arguments) - allowed or not required <= set(arguments):
        raise ValueError("Argumen tool tidak sesuai skema")
    args = arguments
    if name in ("play", "queue_add"):
        values = [args["query"]] if name == "play" else args["queries"]
        if (not values or (name == "queue_add" and len(values) > 50)
                or any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in values)):
            raise ValueError("Query lagu tidak valid")
    elif name == "volume" and (type(args["level"]) is not int or not 0 <= args["level"] <= 100):
        raise ValueError("Volume harus bilangan bulat 0-100")
    elif name == "recommend" and (type(args["count"]) is not int or not 1 <= args["count"] <= 5):
        raise ValueError("Jumlah rekomendasi harus 1-5")
    elif name == "history" and (type(args["limit"]) is not int or not 1 <= args["limit"] <= 50):
        raise ValueError("Batas riwayat harus 1-50")
    elif name == "chat" and (not isinstance(args["reply"], str) or len(args["reply"]) > 500):
        raise ValueError("Balasan chat tidak valid")
    return args

