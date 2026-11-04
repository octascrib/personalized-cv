"""Offline checks: synthetic input, mocked provider, real PDF rendering."""

from contextlib import contextmanager
from datetime import datetime
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

from pypdf import PdfReader

from personalized_cv.cli import main
from personalized_cv.files import output_stem, read_text, reserve_outputs
from personalized_cv.llm import ProviderError, generate
from personalized_cv.models import Claim, Entry, GeneratedCV, JobDetail, Requirement, Section
from personalized_cv.render import find_fonts, render_pdf, verify_pdf

ROOT = Path(__file__).resolve().parents[1]
PROFILE = """Name: Ana Șerban
Email: ana@example.test
Role: Python Developer
Company: Example Studio
Dates: 2022-2025
Built Python APIs and automated tests.
"""
JOB = "Example Labs is hiring a Backend Engineer. Python and automated testing required."


def fixture():
    def claim(text, quote=None):
        return Claim(text=text, profile_quotes=[quote or text])
    return GeneratedCV(
        candidate_name=claim("Ana Șerban"),
        job_title=JobDetail(text="Backend Engineer", job_quote="hiring a Backend Engineer"),
        company=JobDetail(text="Example Labs", job_quote="Example Labs"),
        language="English", contacts=[claim("ana@example.test")],
        sections=[Section(heading="Work Experience", entries=[Entry(
            heading=claim("Python Developer"),
            details=[claim("Example Studio"), claim("2022-2025")],
            bullets=[claim("Built Python APIs and automated tests.")],
        )])],
        requirements=[Requirement(requirement="Python", priority="required", status="supported",
                                  profile_quotes=["Built Python APIs and automated tests."], note="Documented work.")],
        wording_changes=[], warnings=[], clarification_questions=[], max_pages=2,
    )


@contextmanager
def working_directory(path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


class FilesTests(unittest.TestCase):
    def test_automatic_name_and_timezone(self):
        now = datetime(2026, 11, 4, 18, 25, 30, tzinfo=ZoneInfo("Europe/Bucharest"))
        self.assertEqual(output_stem(None, "Ana Șerban", "Backend Engineer", "Example Labs", now),
                         "ana-serban_backend-engineer_example-labs_2026-11-04_18-25-30")

    def test_output_path_traversal_is_rejected(self):
        for value in ("../stolen.pdf", "/tmp/cv.pdf", "folder\\cv.pdf", ".gitkeep", "", "..", "a\nb"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                output_stem(value, "", "", "", datetime.now())

    def test_output_collision_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "cv.pdf").write_bytes(b"existing CV")
            with self.assertRaises(ValueError):
                reserve_outputs(path, "cv", False)
            paths = reserve_outputs(path, "cv", True)
            self.assertEqual(paths["pdf"].name, "cv_001.pdf")
            self.assertEqual((path / "cv.pdf").read_bytes(), b"existing CV")

    def test_partial_reservation_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "cv.md").write_text("original")
            with self.assertRaises(ValueError):
                reserve_outputs(path, "cv", False)
            self.assertFalse((path / "cv.pdf").exists())
            self.assertEqual((path / "cv.md").read_text(), "original")

    def test_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.txt"
            for data in (b"", b" \n", b"\xff", b"binary\x00data"):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    read_text(path)


class SourceTests(unittest.TestCase):
    def test_real_quotes_are_required(self):
        cv = fixture()
        cv.validate_sources(PROFILE, JOB)
        cv.sections[0].entries[0].bullets[0].profile_quotes = ["Invented source"]
        with self.assertRaises(ValueError):
            cv.validate_sources(PROFILE, JOB)

    def test_job_requirements_cannot_be_profile_evidence(self):
        cv = fixture()
        cv.contacts[0].profile_quotes = ["Python and automated testing required."]
        with self.assertRaises(ValueError):
            cv.validate_sources(PROFILE, JOB)

    def test_job_metadata_must_be_in_advertisement(self):
        cv = fixture()
        cv.company.text = "Made-up Company"
        with self.assertRaises(ValueError):
            cv.validate_sources(PROFILE, JOB)


class ProviderTests(unittest.TestCase):
    def test_request_schema_and_response(self):
        response = {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": fixture().model_dump_json()}]}]}
        with patch("personalized_cv.llm.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as call:
            cv = generate(PROFILE, JOB, "template", None, "test-model", "secret-test-key", 30)
        self.assertEqual(cv.candidate_name.text, "Ana Șerban")
        payload = json.loads(call.call_args.args[0].data)
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(json.loads(payload["input"][0]["content"])["candidate_profile"], PROFILE)

    def test_http_error_does_not_expose_provider_body(self):
        error = HTTPError("https://example.test", 401, "sensitive profile", {}, None)
        with patch("personalized_cv.llm.urlopen", side_effect=error), self.assertRaises(ProviderError) as caught:
            generate(PROFILE, JOB, "template", None, "test-model", "secret-test-key", 30)
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertNotIn("secret-test-key", str(caught.exception))

    def test_refusal_and_incomplete_response(self):
        for response in ({"status": "incomplete"}, {"status": "completed", "output": [
                {"type": "message", "content": [{"type": "refusal"}]}]}):
            with patch("personalized_cv.llm.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaises(ProviderError):
                    generate(PROFILE, JOB, "template", None, "test-model", "key", 30)


class PipelineTests(unittest.TestCase):
    def run_cli(self, directory, result, *extra, provider_error=None):
        path = Path(directory)
        (path / "profile.md").write_text(PROFILE)
        (path / "job.txt").write_text(JOB)
        args = ["--profile", "profile.md", "--job", "job.txt", "--template",
                str(ROOT / "cv-templates/01-reverse-chronological.md"), "--model", "test-model", *extra]
        with working_directory(path), patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}), \
                patch("personalized_cv.cli.generate", return_value=result, side_effect=provider_error):
            return main(args)

    def test_full_pipeline_with_real_pdf_and_explicit_name(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertLogs("personalized_cv", level="INFO") as logs:
                code = self.run_cli(directory, fixture(), "--output", "my-cv.pdf")
            self.assertEqual(code, 0)
            output = Path(directory) / "output"
            self.assertEqual({p.name for p in output.iterdir()}, {"my-cv.pdf", "my-cv.md", "my-cv.report.md"})
            self.assertIn("Ana Șerban", PdfReader(output / "my-cv.pdf").pages[0].extract_text())
            self.assertIn("Built Python APIs", (output / "my-cv.md").read_text())
            self.assertIn("pending human review", (output / "my-cv.report.md").read_text())
            self.assertNotIn("Built Python APIs", "\n".join(logs.output))
            self.assertNotIn("fake-key", "\n".join(logs.output))

    def test_automatic_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli(directory, fixture(), "--timezone", "Europe/Bucharest"), 0)
            pdf = next((Path(directory) / "output").glob("*.pdf"))
            self.assertRegex(pdf.name, r"^ana-serban_backend-engineer_example-labs_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d.pdf$")

    def test_missing_job_metadata_has_honest_fallback(self):
        cv = fixture()
        cv.job_title = cv.company = None
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli(directory, cv), 0)
            pdf = next((Path(directory) / "output").glob("*.pdf"))
            self.assertIn("unknown-job_unknown-company", pdf.name)

    def test_unverifiable_content_keeps_report_but_no_pdf(self):
        cv = fixture()
        cv.contacts[0].profile_quotes = ["Invented evidence"]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli(directory, cv, "--output", "invalid"), 1)
            self.assertFalse((Path(directory) / "output/invalid.pdf").exists())
            self.assertTrue((Path(directory) / "output/invalid.report.md").exists())

    def test_blocking_clarification_stops_pdf_generation(self):
        cv = fixture()
        cv.clarification_questions = ["Please clarify the conflicting dates."]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli(directory, cv, "--output", "clarify"), 1)
            self.assertFalse((Path(directory) / "output/clarify.pdf").exists())
            self.assertIn("conflicting dates", (Path(directory) / "output/clarify.report.md").read_text())

    def test_provider_failure_removes_reserved_files(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli(directory, fixture(), "--output", "failed",
                                           provider_error=ProviderError("Test failure")), 1)
            self.assertEqual(list((Path(directory) / "output").glob("failed*")), [])

    def test_existing_output_fails_before_provider_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "output").mkdir()
            (root / "output/existing.pdf").write_bytes(b"original")
            (root / "profile.md").write_text(PROFILE)
            (root / "job.txt").write_text(JOB)
            with working_directory(root), patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}), \
                    patch("personalized_cv.cli.generate") as provider:
                code = main(["--profile", "profile.md", "--job", "job.txt", "--template",
                             str(ROOT / "cv-templates/01-reverse-chronological.md"),
                             "--model", "test-model", "--output", "existing"])
            self.assertEqual(code, 1)
            provider.assert_not_called()
            self.assertEqual((root / "output/existing.pdf").read_bytes(), b"original")

    def test_model_cannot_disable_template_page_limit(self):
        cv = fixture()
        cv.max_pages = None
        cv.sections[0].entries[0].bullets *= 100
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_cli(directory, cv, "--output", "too-long"), 1)
            self.assertFalse((Path(directory) / "output/too-long.pdf").exists())

    def test_duplicate_pdf_text_is_rejected(self):
        cv = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.pdf"
            render_pdf(cv, path, find_fonts(None))
            cv.sections[0].entries[0].bullets = []
            with self.assertRaises(ValueError):
                verify_pdf(cv, path)

    def test_page_limit_rejection(self):
        cv = fixture()
        cv.max_pages = 1
        cv.sections[0].entries[0].bullets *= 100
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "long.pdf"
            render_pdf(cv, path, find_fonts(None))
            with self.assertRaises(ValueError):
                verify_pdf(cv, path)


if __name__ == "__main__":
    unittest.main()
