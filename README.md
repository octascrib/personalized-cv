# personalized-cv

An application for tailoring CVs to job advertisements using an LLM and the
candidate's actual profile.

The intended output is a PDF with selectable, searchable text, without fabricated
experience or qualifications.

## Status

The project contains five independent Markdown templates in `template/`.
Research, sources, and the catalog are documented in
[docs/cv-template-research.md](docs/cv-template-research.md).
The initial Python CLI reads a profile, a job advertisement, and a selected template;
uses OpenAI or a local safetensors model through Transformers; and generates a PDF,
Markdown source, and an adaptation report with live terminal progress logs.

See [CLI setup and usage](docs/cli.md) for installation, configuration, validation,
and current limitations. With dependencies installed and `OPENAI_API_KEY` and
`OPENAI_MODEL` set:

```bash
python -m personalized_cv \
  --profile profile.md \
  --jd job.txt \
  --template 01-reverse-chronological.md
```

For offline generation from an existing model directory, install the optional
`local` extra and add `--provider local --model profile/models/my-instruct-model`.
No OpenAI API key is required in local mode. See the CLI guide for model requirements
and CPU/CUDA installation.

Add `--output my-cv.pdf` to select a filename. Otherwise it is generated from the
candidate name, job title, company, and generation timestamp. Results go to `output/`.

## Repository language

All repository content, documentation, template instructions, code comments, commit
messages, and GitHub descriptions, issues, and pull requests must be in English.
Generated CVs may use the language selected by the user; this does not change the
repository language policy. Keep candidate data and generated documents outside Git.

## Local data

Use the following local directories:

- `profile/`: the candidate's complete source profile and supporting documents.
- `jd/`: job advertisements to use when tailoring a CV.
- `output/`: generated CVs and adaptation reports.

Only the root `.gitkeep` file in each directory is tracked. All other files and
subdirectories inside these directories are ignored, including nested `.gitkeep`
files. Do not force-add personal documents to Git.

Store API keys locally in `.env`, which is also excluded from Git. Do not add
candidates' personal data to templates.
