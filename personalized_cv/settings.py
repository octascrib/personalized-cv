"""Non-secret project defaults stored in setup.json."""

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .files import mapped_input


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1] = 1
    provider: Literal["openai", "local"]
    llm: str
    device: Literal["auto", "cpu", "cuda"] = "auto"
    max_new_tokens: int = Field(default=8192, gt=0)
    timeout: float = Field(default=180, gt=0, allow_inf_nan=False)
    language: str | None = None
    timezone: str | None = None
    font_dir: str | None = None

    @field_validator("llm")
    @classmethod
    def non_empty_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("An LLM name is required.")
        return value.strip()


def load_setup() -> Settings | None:
    path = Path.cwd() / "setup.json"
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 64_000:
            raise ValueError("Oversized setup")
        return Settings.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise ValueError("setup.json is invalid or unsupported. Run --setup --provider ... --llm ... to replace it.") from None


def resolve_settings(args: argparse.Namespace, saved: Settings | None = None) -> Settings:
    provider = args.provider or (saved.provider if saved else os.environ.get("CV_PROVIDER", "openai"))
    variable = "OPENAI_MODEL" if provider == "openai" else "LOCAL_MODEL"
    # A provider override must never reuse the other provider's saved model.
    model = args.model or (saved.llm if saved and saved.provider == provider else os.environ.get(variable))
    if not model:
        raise ValueError(f"Choose an LLM with --llm, --model, --setup, or {variable}.")
    values = {"provider": provider, "llm": model}
    for field in ("device", "max_new_tokens", "timeout", "language", "timezone", "font_dir"):
        explicit = getattr(args, field)
        if explicit is not None:
            values[field] = str(explicit) if field == "font_dir" else explicit
        elif saved is not None:
            values[field] = getattr(saved, field)
        elif field == "timezone" and os.environ.get("CV_TIMEZONE"):
            values[field] = os.environ["CV_TIMEZONE"]
    try:
        settings = Settings.model_validate(values)
    except ValueError:
        raise ValueError("Invalid provider or generation settings; check CLI flags and environment variables.") from None
    if settings.timezone:
        ZoneInfo(settings.timezone)
    if settings.provider == "local":
        mapped_input("llm", Path(settings.llm))
    return settings


def save_setup(settings: Settings) -> Path:
    """Replace defaults atomically; never serialize API credentials."""
    destination = Path.cwd() / "setup.json"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".setup-",
                                         suffix=".tmp", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(settings.model_dump(), stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return destination
