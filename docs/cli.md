# Command-line usage

## Installation

Use Python 3.11 or later. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Install DejaVu Sans fonts through your operating system, or provide a directory
containing `DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` with `--font-dir`.

The default provider is OpenAI's Responses API. Set `OPENAI_API_KEY` and
`OPENAI_MODEL` in your shell. Choose a model available to your account that supports
Structured Outputs. There is deliberately no hard-coded model selection. A `.env`
file is not loaded automatically; `.env.example` lists the environment variables.
Avoid entering credentials in a command that will be retained in shell history.

In OpenAI mode, the entire profile, job advertisement, and template are sent to OpenAI. The request
sets `store` to `false`; this is not a guarantee of zero provider-side retention.
Review the provider's applicable data handling terms before sending personal data.
No real API call is made during the automated tests.

API implementation reference:
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

## One-time project setup

Configure the provider and model without supplying generation inputs:

```bash
.venv/bin/python -m personalized_cv --setup --provider local --llm my-instruct-model
```

The name resolves to `llm/my-instruct-model/`. Setup writes non-secret defaults to
`setup.json` in the current project root; it performs no download, model loading,
or inference and does not require an API key. A missing local model directory is
reported as a warning, so it can be installed before the first generation.

For OpenAI use `--setup --provider openai --llm YOUR_OPENAI_MODEL`. API keys remain
in `OPENAI_API_KEY`, never in the setup file. Both `--provider` and `--llm` (or its
`--model` alias) must be explicit for setup. Do not combine setup with profile, job,
template, or output arguments.

Example saved defaults:

```json
{
  "version": 1,
  "provider": "local",
  "llm": "my-instruct-model",
  "device": "auto",
  "max_new_tokens": 8192,
  "timeout": 180,
  "language": null,
  "timezone": null,
  "font_dir": null
}
```

You can save `--device`, `--max-new-tokens`, `--timeout`, `--language`, `--timezone`,
and `--font-dir` during setup. Rerunning setup replaces the previous configuration
atomically; it also repairs an invalid setup file. An invalid or unsupported file
blocks ordinary generation with a clear error rather than silently changing backend.

Generation precedence is explicit CLI flags, then saved setup defaults, then environment
fallbacks, then built-in defaults. Switching providers explicitly never reuses the
other provider's saved LLM. CLI overrides affect only that invocation. The setup file
and all contents of `llm/` except `.gitkeep` are excluded from Git.

## Generate a CV

Create your UTF-8 profile in `profile/profile.md` and paste the job advertisement
into `jd/job.txt`. Both files are plain text, not PDF or DOCX. Run from the
repository root:

```bash
python -m personalized_cv \
  --profile profile.md \
  --jd job.txt \
  --template 01-reverse-chronological.md
```

The three file arguments are required for generation; provider and LLM are read
from `setup.json` when available. They are resolved relative to designated
directories in the current working directory:

| Argument | Example | Resolved file |
| --- | --- | --- |
| `--profile` | `profile.md` | `profile/profile.md` |
| `--jd` | `job.txt` | `jd/job.txt` |
| `--template` | `01-reverse-chronological.md` | `template/01-reverse-chronological.md` |

Pass filenames without repeating the directory prefix. Relative subpaths such as
`--profile candidates/person.md` are also supported within the designated directory.
Absolute paths, parent-directory traversal, and symlinks escaping that directory are
rejected. Root-level files with the same name are not used as fallbacks. The job
description argument is named `--jd`; the previous `--job` flag has been removed.

Without setup, set the OpenAI model with `OPENAI_MODEL` or the optional `--llm` flag.
Use `--provider local` for direct offline inference. The installed `personalized-cv`
command accepts the same arguments as `python -m personalized_cv`.

To choose the output filename:

```bash
python -m personalized_cv \
  --profile profile.md \
  --jd job.txt \
  --template 03-technical.md \
  --output my-application.pdf \
  --language English \
  --timezone Europe/Bucharest
```

`--output` accepts a filename, not a directory or path. The `.pdf` extension is
optional. All results are saved in `output/` relative to the current working
directory, so running from the repository root keeps them covered by `.gitignore`.
Existing files are never overwritten; an explicit conflicting name fails before
calling the provider.

Without `--output`, the name uses metadata extracted from the sources:

```text
candidate-name_job-title_company_YYYY-MM-DD_HH-MM-SS.pdf
```

Name components are converted to lowercase ASCII slugs. The timestamp is taken
after the model response, using the system local timezone unless `--timezone` or
`CV_TIMEZONE` specifies an IANA timezone. Same-second collisions get `_001`, `_002`,
and so on. Missing job title or company uses `unknown-job` or `unknown-company`;
the report records the missing value. A missing or conflicting candidate identity
blocks final PDF generation.

Each successful run produces:

- `<name>.pdf`: single-column A4 PDF with embedded fonts and selectable text.
- `<name>.md`: the CV's text content.
- `<name>.report.md`: criteria mapping, exact source quotations, wording changes,
  warnings, clarification questions, and verification status.

All three files contain private data and are excluded from Git under `output/`.
Reports are written in English; CV content follows `--language` or the advertisement
language. Proper names, original job titles, and quotations retain their source text.

## Local safetensors inference

Safetensors stores model weights; it is not an inference engine or a complete model
by itself. The local backend uses PyTorch and Hugging Face Transformers directly.
LangChain is not needed for this single-generation workflow. Both backends return
the same structured CV model and share source checks, rendering, naming, and reports.

Install the optional local dependencies into your virtual environment:

```bash
python -m pip install -e '.[local]'
```

For a CPU-only environment, install a CPU build of PyTorch first, then the extra:

```bash
python -m pip install 'torch>=2.6,<3' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e '.[local]'
```

For generation, use a complete, already-downloaded instruction/chat causal language model supported
by `AutoModelForCausalLM`, with `config.json`, `.safetensors` weights (including all
shards if applicable), and its matching tokenizer files and chat template. The chat
template must support system and user messages. A standalone weights file, LoRA
adapter, base model without a chat template, or an arbitrary safetensors checkpoint
is not sufficient. Quantized models requiring additional backends are not configured
by this initial adapter. Check model licensing before obtaining or using weights.

Keep each complete local model in its own directory under `llm/`, for example
`llm/my-instruct-model/`. Never
commit weights. The application does not download models automatically or execute
custom model code (`trust_remote_code=False`). It passes `local_files_only=True`
for tokenizer/model loading and requires `use_safetensors=True` for the weights.

```bash
python -m personalized_cv \
  --provider local \
  --llm my-instruct-model \
  --profile profile.md \
  --jd job.txt \
  --template 03-technical.md \
  --device cpu \
  --max-new-tokens 4096
```

`--llm` (`--model` is an alias) takes a model name or relative subdirectory inside
`llm/` in local mode, and an API model ID in OpenAI mode. Absolute paths and directory
escapes are rejected for local names. `setup.json` provides saved defaults; without
setup, `CV_PROVIDER`, `LOCAL_MODEL`, and `OPENAI_MODEL` remain supported. `LOCAL_MODEL`
also takes a name relative to `llm/`, not a full filesystem path. Local
mode needs no API key and never falls back to cloud inference, including on failure.
Installing dependencies or manually downloading a model requires network access;
local generation from an existing directory does not send profile or advertisement
data to a provider.

`--device auto` selects CUDA when available, otherwise CPU. Explicit `--device cuda`
fails if CUDA is unavailable. CPU inference uses float32 weights; CUDA uses float16.
RAM/VRAM requirements depend on model size; CPU execution can be slow. There is no
quantization, disk offloading, MPS support, or persistent model server in this version.

`--max-new-tokens` defaults to 8192. The schema and template add to the prompt length;
the prompt plus token budget must fit the model's declared context window. Inputs
are not silently truncated. Choose a sufficient context window or reduce the input
length/token budget. `--timeout` controls only OpenAI requests; local loading and
generation are bounded by resources and the token budget, and can be cancelled
with Ctrl+C.

Local decoding is greedy and asks for JSON matching the same schema. Unlike OpenAI
Structured Outputs, this prompt does not enforce the JSON grammar during decoding.
Invalid or truncated JSON fails validation without creating a final PDF. A single
JSON code fence is accepted; surrounding explanations are not silently discarded.
Content quality and schema adherence depend on the selected model.

Terminal logs distinguish loading the tokenizer/weights, local generation, JSON
validation, and PDF work, with a heartbeat while loading/generating. Reports identify
both the provider and model. No candidate input is printed in progress messages.

Implementation references: [Transformers chat templates](https://huggingface.co/docs/transformers/v5.20.2/chat_templating),
[model loading](https://huggingface.co/docs/transformers/en/main_classes/model), and
[installation and offline mode](https://huggingface.co/docs/transformers/en/installation).

## Progress and errors

Progress messages go directly to stderr, including when output is redirected:

```text
18:25:01 INFO Reading and validating input files...
18:25:01 INFO Template selected: 01-reverse-chronological, version 1.0.2
18:25:01 INFO Sending profile, advertisement, and template to OpenAI; generating tailored content...
18:25:11 INFO Waiting for the model response (10s elapsed)...
18:25:18 INFO Saving the adaptation report and checking source quotations...
18:25:18 INFO Preparing CV content...
18:25:18 INFO Rendering a PDF with embedded fonts and selectable text...
18:25:18 INFO Verifying PDF text order and template page limit...
```

These messages describe actual workflow stages, not token-by-token model reasoning
or a simulated completion percentage. Logs do not include profile content or keys;
output paths can contain the candidate name because of the requested filename format.
The OpenAI request timeout defaults to 180 seconds and can be changed with `--timeout`.
There are no automatic paid retries.

Exit codes: `0` for success, `1` for generation/validation failure, `2` for argument
errors, and `130` for cancellation. On failure, an incomplete PDF is removed. A saved
report and draft Markdown may remain for private review. Choose a new output name
or move those files before retrying with the same explicit name.

## Validation and limitations

The application checks the response schema, verifies that source quotations occur
in the profile, escapes model content before rendering, and compares the complete
extracted PDF text with the expected text, including order. The page limit is taken
from template front matter (`max_pages: 1`, `2`, or `null`), not trusted to the model.
Templates without `max_pages` default to two pages. Oversized PDFs fail rather than
silently shrinking the font or dropping content.

Source quotation checks cannot establish the semantic accuracy of every paraphrase,
identify every job requirement, or guarantee ATS acceptance. Section selection and
wording still depend on the LLM. The renderer supports DejaVu Sans glyphs; unsupported
scripts cause a clear failure rather than a broken PDF.

Visual inspection is a manual step in this initial version. The application does
not claim that generated PDFs were visually verified. Open every page and review
content, spacing, page breaks, and the adaptation report before applying.

The renderer currently implements the shared A4 layout in the bundled templates;
editing Markdown layout instructions does not automatically reconfigure renderer
code. The templates guide the LLM's content and section order. Do not use a custom
template with conflicting rendering requirements without updating the renderer.

## Offline tests

```bash
python -m unittest discover -s tests -v
```

Tests use synthetic data, mocked provider responses, and real PDF rendering and text
extraction. They cover safe naming, timezone formatting, collisions, input validation,
source checks, provider errors, page limits, the end-to-end PDF workflow, local backend routing, context limits, and offline
loading flags. Local model calls in the default suite use a mocked Transformers
runtime. With the local extra installed, an additional test creates a tiny random
model, saves real safetensors weights, reloads them, tokenizes a chat prompt, and
runs CPU generation before checking rejection of its invalid CV JSON. This proves
the inference path works, not that the random model can write CVs. The runtime smoke
test passed with PyTorch 2.15.0+cpu and Transformers 5.22.1.

Real CV quality must still be validated with your chosen OpenAI model and key or a
downloaded instruction-tuned local model. GPU execution has not been tested.
