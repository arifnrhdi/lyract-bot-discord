import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    discord_token: str
    groq_api_key: str
    llm_model: str = "openai/gpt-oss-120b"
    database_path: str = "musicbot.sqlite3"


def load_config() -> Config:
    load_dotenv()
    token, key = os.getenv("DISCORD_TOKEN", ""), os.getenv("GROQ_API_KEY", "")
    if not token or not key:
        raise RuntimeError("DISCORD_TOKEN dan GROQ_API_KEY wajib diisi di .env")
    return Config(token, key, os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
                  os.getenv("DATABASE_PATH", "musicbot.sqlite3"))
