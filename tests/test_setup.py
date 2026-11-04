"""Project setup, persistence, precedence, and model-directory mapping."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personalized_cv.cli import main, parser
from personalized_cv.settings import Settings, load_setup, resolve_settings, save_setup
from personalized_cv.llm import ProviderError
from test_cli import fixture, prepare_workspace, working_directory


class SetupTests(unittest.TestCase):
    def test_setup_creates_root_json_without_inputs_key_or_model(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "secret-key"}), \
                patch("personalized_cv.cli.generate_local") as local, \
                patch("personalized_cv.cli.generate") as cloud:
            code = main(["--setup", "local", "--llm", "my-instruct-model"])
            self.assertEqual(code, 0)
            data = json.loads(Path("setup-local.json").read_text())
            self.assertEqual(data["provider"], "local")
            self.assertEqual(data["llm"], "my-instruct-model")
            self.assertNotIn("secret-key", Path("setup-local.json").read_text())
            self.assertFalse(Path("output").exists())
            self.assertFalse(Path("llm/my-instruct-model").exists())
            local.assert_not_called()
            cloud.assert_not_called()

    def test_setup_openai_does_not_require_api_key(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)), \
                patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertEqual(main(["--setup", "remote", "--llm", "test-cloud-model"]), 0)
            self.assertEqual(load_setup("remote").llm, "test-cloud-model")

    def test_setup_requires_explicit_backend_and_llm(self):
        for args in (["--setup"], ["--setup", "--provider", "local"], ["--setup", "--llm", "model"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as caught:
                main(args)
            self.assertEqual(caught.exception.code, 2)

    def test_setup_rejects_generation_arguments(self):
        with self.assertRaises(SystemExit) as caught:
            main(["--setup", "local", "--llm", "model", "--profile", "profile.md"])
        self.assertEqual(caught.exception.code, 2)

    def test_generation_uses_saved_setup_and_mapped_llm(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)):
            root = Path(directory)
            prepare_workspace(root)
            model = root / "llm/my-instruct-model"
            model.mkdir(parents=True)
            (model / "config.json").write_text("{}")
            (model / "model.safetensors").touch()
            self.assertEqual(main(["--setup", "local", "--llm", "my-instruct-model",
                                   "--device", "cpu", "--max-new-tokens", "4096"]), 0)
            with patch.dict(os.environ, {"OPENAI_API_KEY": "", "CV_PROVIDER": "local", "LOCAL_MODEL": "wrong-model"}), \
                    patch("personalized_cv.cli.generate_local", return_value=fixture()) as local, \
                    patch("personalized_cv.cli.generate") as cloud:
                self.assertEqual(main(["--profile", "profile.md", "--jd", "job.txt", "--template",
                                       "01-reverse-chronological.md"]), 0)
            self.assertEqual(local.call_args.args[4], str(model))
            self.assertEqual(local.call_args.args[5:], ("cpu", 4096))
            cloud.assert_not_called()
            self.assertEqual(len(list((root / "output").glob("*.pdf"))), 1)

    def test_explicit_flags_override_saved_defaults(self):
        saved = Settings(provider="openai", llm="saved", timeout=60)
        args = parser().parse_args(["--llm", "override", "--timeout", "30"])
        with patch.dict(os.environ, {"OPENAI_MODEL": "environment"}):
            settings = resolve_settings(args, saved)
        self.assertEqual(settings.llm, "override")
        self.assertEqual(settings.timeout, 30)
        self.assertEqual(saved.llm, "saved")

    def test_provider_switch_never_reuses_other_provider_model(self):
        saved = Settings(provider="local", llm="local-model")
        args = parser().parse_args(["--provider", "openai"])
        with patch.dict(os.environ, {"OPENAI_MODEL": ""}):
            with self.assertRaises(ValueError):
                resolve_settings(args, saved)
        with patch.dict(os.environ, {"OPENAI_MODEL": "cloud-model"}):
            self.assertEqual(resolve_settings(args, saved).llm, "cloud-model")

    def test_invalid_setup_is_reported_and_can_be_replaced(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)):
            for content in ("not json", '{"provider":"unknown"}', '{"version":2,"provider":"local","llm":"model"}',
                            '{"provider":"openai","llm":"model","api_key":"do-not-save"}'):
                Path("setup-local.json").write_text(content)
                with self.assertRaisesRegex(ValueError, "invalid or unsupported"):
                    load_setup()
            self.assertEqual(main(["--setup", "local", "--model", "replacement"]), 0)
            self.assertEqual(load_setup("local").llm, "replacement")
            self.assertFalse(list(Path.cwd().glob(".setup-*.tmp")))

    def test_local_setup_rejects_escape_and_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)):
            save_setup(Settings(provider="openai", llm="previous"))
            for name in ("../model", "/tmp/model", "..\\model"):
                self.assertEqual(main(["--setup", "local", "--llm", name]), 1)
                self.assertEqual(load_setup("remote").llm, "previous")

    def test_setups_coexist_and_runtime_selects_the_right_profile(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)):
            prepare_workspace(Path.cwd())
            model = Path("llm/my-local-model")
            model.mkdir(parents=True)
            (model / "config.json").write_text("{}")
            (model / "model.safetensors").touch()
            self.assertEqual(main(["--setup", "local", "--llm", "my-local-model"]), 0)
            local_before = Path("setup-local.json").read_bytes()
            self.assertEqual(main(["--setup", "remote", "--llm", "my-cloud-model"]), 0)
            self.assertEqual(Path("setup-local.json").read_bytes(), local_before)
            self.assertEqual(load_setup("remote").llm, "my-cloud-model")
            base = ["--profile", "profile.md", "--jd", "job.txt", "--template", "01-reverse-chronological.md"]
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "CV_PROVIDER": "local"}), \
                    patch("personalized_cv.cli.generate_local", return_value=fixture()) as local, \
                    patch("personalized_cv.cli.generate", return_value=fixture()) as remote:
                self.assertEqual(main(base + ["--output", "default-local"]), 0)
                local.assert_called_once()
                remote.assert_not_called()
                local.reset_mock()
                self.assertEqual(main(base + ["--provider", "remote", "--output", "remote-cv"]), 0)
                remote.assert_called_once()
                self.assertEqual(remote.call_args.args[4], "my-cloud-model")
                local.assert_not_called()

    def test_failures_never_switch_backend_in_either_direction(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)):
            prepare_workspace(Path.cwd())
            model = Path("llm/my-local-model")
            model.mkdir(parents=True)
            (model / "config.json").write_text("{}")
            (model / "model.safetensors").touch()
            save_setup(Settings(provider="local", llm="my-local-model"))
            save_setup(Settings(provider="openai", llm="my-cloud-model"))
            base = ["--profile", "profile.md", "--jd", "job.txt", "--template", "01-reverse-chronological.md"]
            for chosen in ("local", "remote"):
                with self.subTest(provider=chosen), patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
                        patch("personalized_cv.cli.generate_local", side_effect=ProviderError("Local failure")) as local, \
                        patch("personalized_cv.cli.generate", side_effect=ProviderError("Remote failure")) as remote:
                    self.assertEqual(main(base + ["--provider", chosen, "--output", chosen]), 1)
                    selected, other = (local, remote) if chosen == "local" else (remote, local)
                    selected.assert_called_once()
                    other.assert_not_called()
                    self.assertFalse((Path("output") / f"{chosen}.pdf").exists())

    def test_remote_only_setup_does_not_trigger_implicit_remote_generation(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)):
            prepare_workspace(Path.cwd())
            save_setup(Settings(provider="openai", llm="cloud-model"))
            with patch.dict(os.environ, {}, clear=True), \
                    patch("personalized_cv.cli.generate_local") as local, \
                    patch("personalized_cv.cli.generate") as remote:
                self.assertEqual(main(["--profile", "profile.md", "--jd", "job.txt", "--template",
                                       "01-reverse-chronological.md"]), 1)
                remote.assert_not_called()
                local.assert_not_called()

    def test_selected_setup_must_match_backend(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)):
            Path("setup-local.json").write_text(Settings(provider="openai", llm="cloud").model_dump_json())
            with self.assertRaises(ValueError):
                load_setup("local")

    def test_missing_setup_preserves_environment_workflow(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(Path(directory)), \
                patch.dict(os.environ, {"CV_PROVIDER": "local", "LOCAL_MODEL": "my-model"}):
            self.assertIsNone(load_setup())
            settings = resolve_settings(parser().parse_args([]))
            self.assertEqual((settings.provider, settings.llm), ("local", "my-model"))


if __name__ == "__main__":
    unittest.main()
