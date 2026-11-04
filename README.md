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

## Configure local and remote modes

For a local model, put its complete files in `llm/my-instruct-model/`, including
`config.json`, safetensors weights, and the matching tokenizer and chat template.
Save local defaults once:

```bash
.venv/bin/python -m personalized_cv --setup local --llm my-instruct-model
```

This creates `setup-local.json`. To also configure OpenAI, choose an available model
supporting Structured Outputs and run:

```bash
.venv/bin/python -m personalized_cv --setup remote --llm YOUR_OPENAI_MODEL
```

This creates `setup-remote.json` without changing the local setup. Set
`OPENAI_API_KEY` in the environment before remote generation; keys are never saved
in either setup file. Setup saves configuration only: no downloads, model loading,
or inference. Repeating setup replaces only the selected mode's defaults.
`--model` remains an alias for `--llm`.

## Generate whenever needed

Save a UTF-8 profile in `profile/profile.md` and a job advertisement in `jd/job.txt`.
Choose local processing explicitly:

```bash
.venv/bin/python -m personalized_cv \
  --provider local \
  --profile profile.md \
  --jd job.txt \
  --template 01-reverse-chronological.md
```

To use OpenAI for an application, change the provider:

```bash
.venv/bin/python -m personalized_cv \
  --provider remote \
  --profile profile.md \
  --jd job.txt \
  --template 01-reverse-chronological.md
```

`local` reads `setup-local.json`; `remote` reads `setup-remote.json` and sends inputs
to OpenAI. `--provider openai` is an alias for `remote`. With no provider flag,
`CV_PROVIDER` is used if set; otherwise local mode is selected, even if only a
remote setup exists. Neither backend automatically falls back to the other on
errors: generation exits with an error and no final PDF.

Input names map to `profile/`, `jd/`, and `template/`. Add `--output my-cv.pdf` to
choose a filename; otherwise it uses the candidate name, job title, company, date,
and time. Results go to `output/` without overwriting existing files.

Explicit flags override the selected setup for that run without modifying it.
Saved defaults override environment defaults. If the selected setup is absent,
provide an LLM explicitly or through the corresponding environment variable;
the other mode's setup is never used. Review the CV and adaptation report before
applying; source checks cannot guarantee factual accuracy or ATS acceptance.

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
are ignored. `setup-local.json`, `setup-remote.json`, temporary setup files, and `.env` credentials are also
ignored. Do not force-add private documents or weights. Environment variables must
be exported in your shell; `.env` is not loaded automatically.
