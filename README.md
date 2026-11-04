# personalized-cv

Tailor a CV to a job advertisement using the candidate's actual profile and an LLM.
Generate a PDF with selectable, searchable text, plus a Markdown draft and an
adaptation report. Progress logs appear directly in the terminal.

## Install

Use Python 3.11 or later and run these commands from the project root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

For local models, also install the optional dependencies:

```bash
.venv/bin/python -m pip install -e '.[local]'
```

Install DejaVu Sans fonts through your operating system. See the
[CLI guide](docs/cli.md) for CPU-only PyTorch installation and font configuration.

## Set up once

For a local model, put its complete files in `llm/my-instruct-model/`, including
`config.json`, safetensors weights, and the matching tokenizer and chat template.
Then run:

```bash
.venv/bin/python -m personalized_cv --setup --provider local --llm my-instruct-model
```

This creates `setup.json` in the project root. Setup saves defaults only: it does
not download, load, or run the model. You may configure the name before installing
the model, but its complete files must be present before generating a CV.

For OpenAI instead, choose a model available to your account that supports
Structured Outputs and set the `OPENAI_API_KEY` environment variable for generation:

```bash
.venv/bin/python -m personalized_cv --setup --provider openai --llm YOUR_OPENAI_MODEL
```

The API key is never saved in `setup.json`. Both this file and model weights are
excluded from Git. Rerun setup to replace the saved defaults. `--model` is an alias
for `--llm`; local model names are always resolved inside `llm/`.

## Generate whenever needed

Save a UTF-8 candidate profile in `profile/profile.md` and a job advertisement in
`jd/job.txt`, then run:

```bash
.venv/bin/python -m personalized_cv \
  --profile profile.md \
  --jd job.txt \
  --template 01-reverse-chronological.md
```

The command reads the provider and LLM from `setup.json`. Input names map to
`profile/`, `jd/`, and `template/`, respectively. Add `--output my-cv.pdf` to choose
a filename; otherwise it uses the candidate name, job title, company, date, and time.
The PDF, Markdown source, and report are saved in `output/` without overwriting
existing files.

Explicit flags override saved defaults for that run without changing `setup.json`.
Saved defaults override environment defaults. Local mode needs no API key and never
falls back to cloud inference. Review the CV and adaptation report before applying;
source checks cannot guarantee factual accuracy or ATS acceptance.

## Templates and documentation

Five self-contained Markdown templates are available in `template/`. See the
[research and catalog](docs/cv-template-research.md) and the
[CLI guide](docs/cli.md) for supported models, options, validation, and limitations.

## Repository language and local files

All repository content, template instructions, code comments, commit messages, and
GitHub descriptions, issues, and pull requests must be in English. Generated CVs may
use the user's chosen language; candidate data and generated documents stay out of Git.

- `profile/`: candidate profiles and supporting documents.
- `jd/`: job advertisements.
- `llm/`: complete local model directories.
- `output/`: generated CVs and reports.

Only each directory's root `.gitkeep` is tracked; all other files and subdirectories
are ignored. `setup.json`, temporary setup files, and `.env` credentials are also
ignored. Do not force-add private documents or weights. Environment variables must
be exported in your shell; `.env` is not loaded automatically.
