from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root() -> Path:
    # PyInstaller / frozen exe: keep .env, voices/, data/ beside the .exe
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    here = Path(__file__).resolve()
    candidates = [here.parent, *here.parents]
    for p in candidates:
        if (p / "pyproject.toml").exists() and (p / "src").exists():
            return p
        if (p / "voices").is_dir() and (p / "README.md").exists():
            return p
    return Path.cwd()


ROOT = _find_root()
DATA_DIR = ROOT / "data"
VOICES_DIR = ROOT / "voices"


class PersonaId(str, Enum):
    STRATEGIST = "strategist"
    AGGRESSIVE = "aggressive"
    DATA_GEEK = "data_geek"
    VETERAN = "veteran"


class Gender(str, Enum):
    MAN = "man"
    WOMAN = "woman"


class Region(str, Enum):
    US = "us"
    UK = "uk"
    SPAIN = "spain"
    ITALY = "italy"
    BRAZIL = "brazil"
    GERMANY = "germany"
    JAPAN = "japan"


class Talkativeness(str, Enum):
    QUIET = "quiet"
    NORMAL = "normal"
    CHATTY = "chatty"


class VoiceBackend(str, Enum):
    AUTO = "auto"
    ELEVENLABS = "elevenlabs"
    LOCAL_CLONE = "local_clone"
    EDGE = "edge"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    elevenlabs_api_key: str = ""

    udp_host: str = "127.0.0.1"
    udp_port: int = 20777

    engineer_persona: PersonaId = PersonaId.STRATEGIST
    engineer_gender: Gender = Gender.WOMAN
    engineer_region: Region = Region.US
    voice_backend: VoiceBackend = VoiceBackend.AUTO
    talkativeness: Talkativeness = Talkativeness.NORMAL
    ptt_hotkey: str = "grave"
    radio_fx: bool = True
    mute_audio: bool = False
    mock_telemetry: bool = False

    voice_profile_id: str = Field(default="", description="Override voice profile id")


def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    (VOICES_DIR / "custom").mkdir(parents=True, exist_ok=True)
    return Settings()
