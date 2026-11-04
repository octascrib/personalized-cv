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

The initial provider is OpenAI's Responses API. Set `OPENAI_API_KEY` and
`OPENAI_MODEL` in your shell. Choose a model available to your account that supports
Structured Outputs. There is deliberately no hard-coded model selection. A `.env`
file is not loaded automatically; `.env.example` lists the environment variables.
Avoid entering credentials in a command that will be retained in shell history.

The entire profile, job advertisement, and template are sent to OpenAI. The request
sets `store` to `false`; this is not a guarantee of zero provider-side retention.
Review the provider's applicable data handling terms before sending personal data.
No real API call is made during the automated tests.

API implementation reference:
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

## Generate a CV

Create your UTF-8 profile in `private/profile.md` and paste the job advertisement
into `input/job.txt`. Both files are plain text, not PDF or DOCX. Run from the
repository root:

```bash
python -m personalized_cv \
  --profile private/profile.md \
  --job input/job.txt \
  --template cv-templates/01-reverse-chronological.md
```

The three file arguments are required. Set the model with `OPENAI_MODEL` or the
optional `--model` flag. The installed `personalized-cv` command accepts the same
arguments as `python -m personalized_cv`.

To choose the output filename:

```bash
python -m personalized_cv \
  --profile private/profile.md \
  --job input/job.txt \
  --template cv-templates/03-technical.md \
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
The provider timeout defaults to 180 seconds and can be changed with `--timeout`.
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
source checks, provider errors, page limits, and the end-to-end local workflow.
A real provider request must still be validated with your chosen model and key.
