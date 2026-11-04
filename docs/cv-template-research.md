# CV structure research and template catalog

Reviewed on: **November 4, 2026**. This summarizes guidance available on that date.
It is not a statistical study establishing that a format is more popular in 2026
or improves hiring rates.

## Findings from sources

- **Readability and data extraction.** Greenhouse lists columns, tables, images,
  and contact details in headers or footers as potential parsing problems. This
  supports the conservative choice of a single column with real text. A parsing
  error does not establish automatic candidate rejection.
  [Greenhouse - Unsuccessful resume parse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse)
- **Simple formatting.** CareerOneStop recommends conventional headings, consistent
  spacing, readable fonts, and one or two pages for typical professional resumes.
  It recommends PDF unless the employer specifies otherwise. Length is not universal.
  [CareerOneStop - Formatting](https://cloudfront.careeronestop.org/JobSearch/Resumes/ResumeGuide/formatting.aspx)
- **Authentic AI-assisted tailoring.** Harvard describes AI-assisted wording revisions
  and relevant keywords while preserving an authentic representation of the candidate.
  In this project, every rephrased claim must remain linked to profile evidence.
  [Harvard - Create a Strong Resume](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)
- **Structure depends on career history.** Oxford describes reverse chronological
  and skills-based formats for transitions. We chose a career-change hybrid so
  transferable skill evidence does not replace dated employment history.
  [Oxford - CVs](https://www.ox.ac.uk/careers/careers-guidance/job-search-and-applications/writing-applications/cvs)
- **One profile, multiple applications.** Europass supports selecting profile information
  and tailoring a CV to an opportunity. This supports our workflow: complete profile,
  selection for a job advertisement, separate document. We do not reproduce Europass
  design or claim our files are official Europass documents.
  [Europass - Create your CV](https://europass.europa.eu/en/create-europass-cv)
- **Academic exceptions.** Oxford describes sections for research, publications, and
  teaching. It also discusses narrative CVs required by some funders; these need
  institutional instructions rather than a generic professional template.
  [Oxford - Academic applications](https://www.ox.ac.uk/careers/careers-guidance/job-search-and-applications/writing-applications/academic-applications)

## Project decisions

The templates are an original synthesis, not copies of institutional templates.
There is no evidence here that every portal accepts PDF or that a layout achieves
any universal "ATS score." Employer instructions take precedence for submission
format, length, and required forms.

The default documents exclude photographs. Regional guidance differs: Europass,
for example, suggests a photograph, while other sources identify parsing risks.
We do not treat a regional convention as a global rule. An explicit conflicting
requirement should be discussed before using these templates.

A4 pages, 20 mm margins, 11 pt body text, suggested bullet counts, and a separate
adaptation report are product and implementation choices, not proven ATS
requirements. The initial collection has no purely functional or infographic
template; it preserves employment context and a simple reading order.

## Catalog

| File in `cv-templates/` | Use case | Suggested length |
| --- | --- | --- |
| `01-reverse-chronological.md` | Default; relevant experience, including senior roles | 1-2 pages |
| `02-early-career.md` | Students, graduates, internships, first jobs | 1 page |
| `03-technical.md` | Technical roles with documented tools and projects | 1-2 pages |
| `04-career-change.md` | Career transitions with skill evidence and employment history | 1-2 pages |
| `05-academic.md` | Research and academic posts | Institutional requirements |

Each file is self-contained and includes the input contract, factual accuracy rules,
structure, PDF specification, and checks. Shared rules are intentionally repeated:
an LLM receiving a single template must have all applicable instructions. When
changing shared rules, update all five files and their versions.

## Application integration design

1. List only `cv-templates/*.md`, read metadata, and validate the selected template.
   Keep this research document outside the template catalog.
2. An explicit user selection takes precedence. If the application recommends a
   template automatically, explain the choice using the profile and advertisement.
3. Send template instructions separately from the two inputs delimited as data.
   Markdown instructions against prompt injection do not replace application isolation.
4. The LLM produces content and a provenance report. Validate the data and pass it
   to a controlled renderer, such as ReportLab. Do not execute LLM-generated code
   or allow automatic loading of external resources.
5. The renderer produces a text-based PDF; the application then checks extraction
   and layout. Before sending data to an LLM provider, explain what personal data
   will be sent and to whom. Avoid logging profiles or API keys.

**Current status:** the initial CLI integrates OpenAI structured output, exact
source-quotation checks, PDF rendering, and text extraction checks. Visual inspection
remains manual. No real ATS portal validation or live-provider generation has been
performed. See [CLI usage and limitations](cli.md).
