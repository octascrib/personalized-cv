"""Local-only Transformers inference from a complete safetensors model directory."""

import json
import logging
from pathlib import Path
import re

from .llm import INSTRUCTIONS, ProviderError
from .models import GeneratedCV

LOG = logging.getLogger("personalized_cv")


def validate_model_directory(model: str) -> Path:
    path = Path(model).expanduser().resolve()
    if not path.is_dir():
        raise ProviderError("--model must point to an existing local model directory, not a Hub ID or a weights file.")
    if not (path / "config.json").is_file() or not any(file.is_file() for file in path.glob("*.safetensors")):
        raise ProviderError("The local model directory needs config.json and .safetensors weights, plus its tokenizer files.")
    return path


def load_runtime():
    """Keep large optional dependencies out of OpenAI-only installations."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from transformers.utils import logging as transformers_logging
    except ImportError:
        raise ProviderError("Local inference dependencies are missing; install the optional extra with pip install -e '.[local]'.") from None
    transformers_logging.set_verbosity_error()
    transformers_logging.disable_progress_bar()
    return torch, AutoTokenizer, AutoModelForCausalLM


def parse_local_response(text: str) -> GeneratedCV:
    text = text.strip()
    # Accept a single JSON code fence, but never salvage a guessed JSON substring.
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return GeneratedCV.model_validate_json(text)
    except ValueError:
        raise ProviderError("The local model returned invalid CV JSON. Try an instruction-tuned model or a larger token budget; no PDF was generated.") from None


def generate_local(profile: str, job: str, template: str, language: str | None,
                   model: str, device: str, max_new_tokens: int, dtype: str = "auto") -> GeneratedCV:
    path = validate_model_directory(model)
    torch, AutoTokenizer, AutoModelForCausalLM = load_runtime()
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise ProviderError("CUDA was requested but is unavailable. Use --device cpu or install a compatible PyTorch/CUDA build.")
    if dtype == "auto":
        dtype = "float32" if device == "cpu" else "float16"
    if dtype not in ("float32", "bfloat16", "float16"):
        raise ProviderError("Unsupported local compute dtype.")
    compute_dtype = getattr(torch, dtype)
    LOG.info("Loading the local tokenizer and safetensors weights on %s in %s (offline)...", device, dtype)
    try:
        tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
        if not tokenizer.chat_template:
            raise ProviderError("The local tokenizer has no chat template; choose a supported instruction/chat model.")
        local_model = AutoModelForCausalLM.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False, use_safetensors=True,
            dtype=compute_dtype,
        ).to(device).eval()
        messages = [
            {"role": "system", "content": INSTRUCTIONS + "\n\nTEMPLATE INSTRUCTIONS:\n" + template
             + "\n\nReturn exactly one JSON object matching this schema, with all required keys:\n"
             + json.dumps(GeneratedCV.model_json_schema())},
            {"role": "user", "content": json.dumps({
                "candidate_profile": profile, "job_advertisement": job,
                "output_language": language,
            }, ensure_ascii=False)},
        ]
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True,
        ).to(device)
        input_length = inputs["input_ids"].shape[-1]
        text_config = getattr(local_model.config, "text_config", local_model.config)
        context_limits = [getattr(text_config, "max_position_embeddings", None),
                          getattr(text_config, "n_positions", None),
                          getattr(tokenizer, "model_max_length", None)]
        context_limits = [limit for limit in context_limits if isinstance(limit, int) and 0 < limit < 10_000_000]
        if context_limits and input_length + max_new_tokens > min(context_limits):
            raise ProviderError("The prompt and token budget exceed the local model context window. Shorten the inputs or lower --max-new-tokens; no input was truncated.")
        pad_id = tokenizer.pad_token_id
        if pad_id is None:
            pad_id = tokenizer.eos_token_id
        if pad_id is None:
            raise ProviderError("The local tokenizer needs a padding or end-of-sequence token.")
        LOG.info("Generating CV JSON locally (%d input tokens; up to %d new tokens)...", input_length, max_new_tokens)
        with torch.inference_mode():
            generated = local_model.generate(**inputs, max_new_tokens=max_new_tokens,
                                             do_sample=False, pad_token_id=pad_id)
        new_tokens = generated[0][input_length:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    except ProviderError:
        raise
    except Exception:
        # Third-party exceptions can include prompts. Do not echo their messages.
        raise ProviderError("Local model loading or inference failed. Check model/tokenizer compatibility, available RAM/VRAM, and the installed PyTorch build. No cloud fallback was attempted.") from None
    finally:
        # The one-shot CLI exits after generation; release weights before PDF work.
        if "local_model" in locals():
            del local_model
    LOG.info("Local inference finished; validating the returned JSON...")
    return parse_local_response(text)
