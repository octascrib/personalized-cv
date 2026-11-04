"""Input handling, template metadata, and safe output names."""

from datetime import datetime
from pathlib import Path
import re
import unicodedata

MAX_INPUT_BYTES = 200_000


def mapped_input(directory: str, name: Path) -> Path:
    """Resolve mapped inputs; local model links may target external storage."""
    base = (Path.cwd() / directory).resolve()
    if name.is_absolute() or ".." in name.parts or "\\" in str(name):
        raise ValueError(f"Use a filename or relative subpath inside {directory}/, not an absolute path or traversal.")
    path = (base / name).resolve()
    if directory != "llm" and not path.is_relative_to(base):
        raise ValueError(f"The input must remain inside {directory}/, including symlink targets.")
    return path


def read_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Input file does not exist: {path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"Input file exceeds {MAX_INPUT_BYTES:,} bytes: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeError:
        raise ValueError(f"Input must be UTF-8 text, not PDF, DOCX, or an image: {path}") from None
    if not text.strip() or "\x00" in text:
        raise ValueError(f"Input must contain non-empty plain text: {path}")
    return text


def template_metadata(text: str) -> dict[str, str]:
    parts = text.split("---", 2)
    if not text.startswith("---\n") or len(parts) != 3:
        raise ValueError("The template must start with Markdown front matter.")
    metadata = {}
    for line in parts[1].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip()
    if not all(metadata.get(key) for key in ("id", "version")):
        raise ValueError("The template needs an id and version in its front matter.")
    limit = metadata.get("max_pages", "2")
    if limit != "null" and (not limit.isdigit() or not 1 <= int(limit) <= 100):
        raise ValueError("Template max_pages must be null or an integer from 1 to 100.")
    return metadata


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60].rstrip("-")


def output_stem(explicit: str | None, name: str, job: str, company: str, now: datetime) -> str:
    if explicit is not None:
        if (explicit in ("", ".", "..", ".gitkeep") or "/" in explicit or "\\" in explicit
                or any(ord(c) < 32 for c in explicit) or explicit.startswith(".")):
            raise ValueError("--output must be a plain filename, not a path or hidden file.")
        stem = explicit[:-4] if explicit.lower().endswith(".pdf") else explicit
        if not stem.strip() or len(stem.encode("utf-8")) > 180:
            raise ValueError("Output filename must be non-empty and at most 180 UTF-8 bytes.")
        return stem
    return "_".join((slug(name) or "candidate", slug(job) or "unknown-job",
                     slug(company) or "unknown-company", now.strftime("%Y-%m-%d_%H-%M-%S")))


def reserve_outputs(directory: Path, stem: str, automatic: bool) -> dict[str, Path]:
    """Atomically reserve all output names, never replacing existing user files."""
    suffixes = {"pdf": ".pdf", "markdown": ".md", "report": ".report.md"}
    for index in range(1000):
        candidate = stem if index == 0 else f"{stem}_{index:03d}"
        paths = {key: directory / (candidate + suffix) for key, suffix in suffixes.items()}
        created = []
        try:
            for path in paths.values():
                with path.open("xb"):
                    pass
                created.append(path)
            return paths
        except FileExistsError:
            for path in created:
                path.unlink()
            if not automatic:
                raise ValueError("An output file already exists; choose another --output name.") from None
        except OSError:
            for path in created:
                path.unlink(missing_ok=True)
            raise
    raise ValueError("Could not reserve a unique output filename.")
