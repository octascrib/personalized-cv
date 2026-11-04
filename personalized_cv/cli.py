"""Command-line workflow with progress logs and safe failure handling."""

import argparse
from contextlib import contextmanager
from datetime import datetime
import logging
import math
import os
from pathlib import Path
import sys
from threading import Event, Thread
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .files import mapped_input, output_stem, read_text, reserve_outputs, template_metadata
from .llm import ProviderError, generate
from .local_llm import generate_local, validate_model_directory
from .render import find_fonts, markdown, render_pdf, verify_pdf
from .report import adaptation_report
from .settings import load_setup, normalize_provider, resolve_settings, save_setup, selected_provider, setup_path

LOG = logging.getLogger("personalized_cv")


def positive_timeout(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return number


def positive_integer(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("token budget must be a positive integer")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Tailor a CV using OpenAI or a local model and export a selectable-text PDF into output/.",
        epilog="OpenAI mode sends inputs to OpenAI. Local mode loads an existing model directory offline. "
               "Review the generated CV and report before applying.",
    )
    result.add_argument("--setup", choices=("local", "remote"), help="Save setup-local.json or setup-remote.json; no generation")
    result.add_argument("--profile", type=Path, help="UTF-8 candidate filename relative to profile/ (.md or .txt)")
    result.add_argument("--jd", type=Path, help="UTF-8 job description filename relative to jd/ (.md or .txt)")
    result.add_argument("--template", type=Path, help="Markdown template filename relative to template/")
    result.add_argument("--output", help="Optional filename inside output/; .pdf is optional")
    result.add_argument("--provider", choices=("local", "remote", "openai"), default=None,
                        help="Select local or remote setup; openai aliases remote (default: CV_PROVIDER or local)")
    result.add_argument("--llm", "--model", dest="model", help="OpenAI model ID or local model name relative to llm/; --model is an alias")
    result.add_argument("--device", choices=("auto", "cpu", "cuda"), default=None,
                        help="Local model device; auto selects CUDA if available, otherwise CPU")
    result.add_argument("--dtype", choices=("auto", "float32", "bfloat16", "float16"),
                        help="Local compute precision; auto uses float32 on CPU and float16 on CUDA")
    result.add_argument("--max-new-tokens", type=positive_integer, default=None,
                        help="Local generation token budget (default: 8192)")
    result.add_argument("--language", help="Output language; defaults to the advertisement language")
    result.add_argument("--timezone", default=None,
                        help="IANA timezone for filenames; defaults to the system local timezone")
    result.add_argument("--timeout", type=positive_timeout, default=None, help="OpenAI request timeout in seconds (default: 180); not used locally")
    result.add_argument("--font-dir", type=Path, help="Directory containing DejaVuSans.ttf and DejaVuSans-Bold.ttf")
    return result


@contextmanager
def progress(activity: str = "Waiting for the model response"):
    stop = Event()
    started = time.monotonic()
    def heartbeat():
        while not stop.wait(10):
            LOG.info("%s (%ds elapsed)...", activity, time.monotonic() - started)
    thread = Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    LOG.info("Reading and validating input files...")
    profile, job, template = (
        read_text(mapped_input(directory, name))
        for directory, name in (("profile", args.profile), ("jd", args.jd), ("template", args.template))
    )
    metadata = template_metadata(template)
    fonts = find_fonts(args.font_dir)
    timezone = ZoneInfo(args.timezone) if args.timezone else None
    if args.output is not None:
        output_stem(args.output, "", "", "", datetime.now())
    api_key = ""
    if args.provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Set OPENAI_API_KEY in your environment before generating a CV.")
    else:
        args.model = str(mapped_input("llm", Path(args.model)))
        validate_model_directory(args.model)
    # Setting the environment is intentional: .env files are not silently loaded.
    output_dir = Path.cwd() / "output"
    output_dir.mkdir(exist_ok=True)
    paths = None
    report_saved = False
    try:
        if args.output is not None:
            stem = output_stem(args.output, "", "", "", datetime.now())
            paths = reserve_outputs(output_dir, stem, automatic=False)
        LOG.info("Template selected: %s, version %s", metadata["id"], metadata["version"])
        if args.provider == "openai":
            LOG.info("Sending profile, advertisement, and template to OpenAI; generating tailored content...")
            with progress():
                cv = generate(profile, job, template, args.language, args.model, api_key, args.timeout)
        else:
            LOG.info("Using the local backend; profile and advertisement remain on this machine.")
            with progress("Local model processing"):
                cv = generate_local(profile, job, template, args.language, args.model,
                                    args.device, args.max_new_tokens, dtype=args.dtype)
        # Page limits are application/template policy, never a model-controlled override.
        limit = metadata.get("max_pages", "2")
        cv.max_pages = None if limit == "null" else int(limit)
        if cv.job_title is None:
            cv.warnings.append("Job title not found; the automatic filename uses unknown-job.")
        if cv.company is None:
            cv.warnings.append("Company not found; the automatic filename uses unknown-company.")
        generated_at = datetime.now(timezone) if timezone else datetime.now().astimezone()
        if paths is None:
            stem = output_stem(None, cv.candidate_name.text,
                               cv.job_title.text if cv.job_title else "",
                               cv.company.text if cv.company else "", generated_at)
            paths = reserve_outputs(output_dir, stem, automatic=True)
        LOG.info("Saving the adaptation report and checking source quotations...")
        paths["report"].write_text(adaptation_report(
            cv, metadata, args.model, generated_at, "not yet performed", args.provider), encoding="utf-8")
        report_saved = True
        cv.validate_sources(profile, job)
        if any(not section.heading.strip() or not section.entries for section in cv.sections):
            raise ValueError("The response contains an empty section.")
        if any(not (entry.heading or entry.details or entry.bullets)
               for section in cv.sections for entry in section.entries):
            raise ValueError("The response contains an empty entry.")
        LOG.info("Preparing CV content...")
        paths["markdown"].write_text(markdown(cv), encoding="utf-8")
        LOG.info("Rendering a PDF with embedded fonts and selectable text...")
        render_pdf(cv, paths["pdf"], fonts)
        LOG.info("Verifying PDF text order and template page limit...")
        pages = verify_pdf(cv, paths["pdf"])
        paths["report"].write_text(adaptation_report(
            cv, metadata, args.model, generated_at,
            f"text extraction and order checked; {pages} page(s) within the declared limit", args.provider), encoding="utf-8")
        LOG.info("Done in %.1fs. PDF: %s", time.monotonic() - started, paths["pdf"])
        LOG.info("CV source: %s", paths["markdown"])
        LOG.info("Adaptation report: %s", paths["report"])
        LOG.info("Visual review is still required before submitting the CV.")
        return 0
    except BaseException:
        if paths:
            paths["pdf"].unlink(missing_ok=True)
            # Keep private diagnostic content only if a report was successfully saved.
            if not report_saved:
                paths["markdown"].unlink(missing_ok=True)
                paths["report"].unlink(missing_ok=True)
            else:
                if paths["markdown"].stat().st_size == 0:
                    paths["markdown"].unlink(missing_ok=True)
                LOG.error("No final PDF was kept. Review the private report: %s", paths["report"])
        raise


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stderr)
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    if args.setup:
        if not args.model:
            argument_parser.error("--setup requires --llm (or --model)")
        if args.provider and normalize_provider(args.provider) != normalize_provider(args.setup):
            argument_parser.error("--provider conflicts with the selected --setup mode")
        args.provider = normalize_provider(args.setup)
        if any((args.profile, args.jd, args.template, args.output)):
            argument_parser.error("--setup cannot be combined with generation input/output arguments")
    elif not all((args.profile, args.jd, args.template)):
        argument_parser.error("generation requires --profile, --jd, and --template")
    try:
        # Setup replaces defaults without depending on a previous, possibly broken file.
        if not args.setup:
            args.provider = selected_provider(args)
        saved = None if args.setup else load_setup(args.provider)
        settings = resolve_settings(args, saved)
        if args.setup:
            path = save_setup(settings)
            LOG.info("Project defaults saved to %s. No model was downloaded or inference performed.", path)
            if settings.provider == "local" and not mapped_input("llm", Path(settings.llm)).is_dir():
                LOG.warning("The local model is not installed yet. Place its complete files in llm/%s before generation.", settings.llm)
            return 0
        if saved:
            LOG.info("Loaded project defaults from %s.", setup_path(settings.provider).name)
        args.provider, args.model = settings.provider, settings.llm
        for field in ("device", "dtype", "max_new_tokens", "timeout", "language", "timezone"):
            setattr(args, field, getattr(settings, field))
        args.font_dir = Path(settings.font_dir) if settings.font_dir else None
        return run(args)
    except (ValueError, ProviderError, OSError, ZoneInfoNotFoundError) as exc:
        LOG.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        LOG.error("Generation cancelled.")
        return 130
    except Exception:
        # Third-party exceptions can contain candidate text. Keep logs concise/private.
        LOG.error("Generation failed unexpectedly. No final PDF was kept.")
        return 1
