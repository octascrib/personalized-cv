# personalized-cv

An application for tailoring CVs to job advertisements using an LLM and the
candidate's actual profile.

The intended output is a PDF with selectable, searchable text, without fabricated
experience or qualifications.

## Status

The project contains five independent Markdown templates in `cv-templates/`.
Research, sources, and the catalog are documented in
[docs/cv-template-research.md](docs/cv-template-research.md).
LLM integration and the PDF generator are not implemented yet.

## Repository language

All repository content, documentation, template instructions, code comments, commit
messages, and GitHub descriptions, issues, and pull requests must be in English.
Generated CVs may use the language selected by the user; this does not change the
repository language policy. Keep candidate data and generated documents outside Git.

## Local data

Use the following local directories:

- `private/`: the candidate's complete source profile and supporting documents.
- `input/`: job advertisements to use when tailoring a CV.
- `output/`: generated CVs and adaptation reports.

Only the root `.gitkeep` file in each directory is tracked. All other files and
subdirectories inside these directories are ignored, including nested `.gitkeep`
files. Do not force-add personal documents to Git.

Store API keys locally in `.env`, which is also excluded from Git. Do not add
candidates' personal data to templates.
