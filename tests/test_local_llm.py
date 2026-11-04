"""Offline tests of provider routing and Transformers integration contracts."""

from contextlib import nullcontext
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from personalized_cv.cli import main
from personalized_cv.llm import ProviderError
from personalized_cv.local_llm import generate_local, parse_local_response, validate_model_directory
from test_cli import ROOT, PROFILE, JOB, fixture, working_directory


class Batch(dict):
    def to(self, device):
        self.device = device
        return self


class LocalTests(unittest.TestCase):
    def model_directory(self, root):
        path = Path(root) / "model"
        path.mkdir()
        (path / "config.json").write_text("{}")
        (path / "model.safetensors").touch()
        return path

    def runtime(self, output=None, context=32768):
        torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False),
                                float32="float32", float16="float16", inference_mode=nullcontext)
        tokenizer = MagicMock()
        tokenizer.chat_template = "test chat template"
        tokenizer.model_max_length = context
        tokenizer.pad_token_id = 0
        tokenizer.eos_token_id = 1
        tokenizer.apply_chat_template.return_value = Batch(input_ids=SimpleNamespace(shape=(1, 10)))
        tokenizer.decode.return_value = output if output is not None else fixture().model_dump_json()
        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = model
        model.config = SimpleNamespace(max_position_embeddings=context)
        model.generate.return_value = [list(range(20))]
        tokenizer_class = SimpleNamespace(from_pretrained=MagicMock(return_value=tokenizer))
        model_class = SimpleNamespace(from_pretrained=MagicMock(return_value=model))
        return (torch, tokenizer_class, model_class), tokenizer, model

    def test_model_requires_a_complete_local_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProviderError):
                validate_model_directory(str(Path(directory) / "missing"))
            with self.assertRaises(ProviderError):
                validate_model_directory(directory)
            path = self.model_directory(directory)
            self.assertEqual(validate_model_directory(str(path)), path.resolve())
            with self.assertRaises(ProviderError):
                validate_model_directory(str(path / "model.safetensors"))

    def test_load_flags_and_prompt_separation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.model_directory(directory)
            runtime, tokenizer, model = self.runtime()
            with patch("personalized_cv.local_llm.load_runtime", return_value=runtime):
                result = generate_local(PROFILE, JOB, "template rules", None, str(path), "auto", 2048)
            self.assertEqual(result.candidate_name.text, "Ana Șerban")
            runtime[1].from_pretrained.assert_called_once_with(str(path), local_files_only=True, trust_remote_code=False)
            flags = runtime[2].from_pretrained.call_args.kwargs
            self.assertTrue(flags["use_safetensors"])
            self.assertTrue(flags["local_files_only"])
            self.assertFalse(flags["trust_remote_code"])
            self.assertEqual(flags["dtype"], "float32")
            messages = tokenizer.apply_chat_template.call_args.args[0]
            self.assertIn("template rules", messages[0]["content"])
            self.assertNotIn(PROFILE, messages[0]["content"])
            self.assertEqual(json.loads(messages[1]["content"])["candidate_profile"], PROFILE)
            self.assertEqual(tokenizer.decode.call_args.args[0], list(range(10, 20)))
            self.assertFalse(model.generate.call_args.kwargs["do_sample"])
            self.assertEqual(model.generate.call_args.kwargs["pad_token_id"], 0)

    def test_json_fence_is_accepted_but_explanatory_text_is_not(self):
        text = fixture().model_dump_json()
        self.assertEqual(parse_local_response(f"```json\n{text}\n```").language, "English")
        for invalid in ("Here is your CV: " + text, "{}", text + " trailing text"):
            with self.assertRaises(ProviderError):
                parse_local_response(invalid)

    def test_context_overflow_stops_before_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.model_directory(directory)
            runtime, _, model = self.runtime(context=64)
            with patch("personalized_cv.local_llm.load_runtime", return_value=runtime):
                with self.assertRaisesRegex(ProviderError, "context window"):
                    generate_local(PROFILE, JOB, "template", None, str(path), "cpu", 100)
            model.generate.assert_not_called()

    def test_missing_chat_template_stops_before_loading_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.model_directory(directory)
            runtime, tokenizer, _ = self.runtime()
            tokenizer.chat_template = None
            with patch("personalized_cv.local_llm.load_runtime", return_value=runtime):
                with self.assertRaisesRegex(ProviderError, "chat template"):
                    generate_local(PROFILE, JOB, "template", None, str(path), "cpu", 100)
            runtime[2].from_pretrained.assert_not_called()

    def test_cuda_unavailable_does_not_silently_switch_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.model_directory(directory)
            runtime, _, _ = self.runtime()
            with patch("personalized_cv.local_llm.load_runtime", return_value=runtime):
                with self.assertRaisesRegex(ProviderError, "CUDA"):
                    generate_local(PROFILE, JOB, "template", None, str(path), "cuda", 100)
            runtime[2].from_pretrained.assert_not_called()

    def test_runtime_errors_do_not_echo_candidate_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.model_directory(directory)
            runtime, _, model = self.runtime()
            model.generate.side_effect = RuntimeError(PROFILE)
            with patch("personalized_cv.local_llm.load_runtime", return_value=runtime):
                with self.assertRaises(ProviderError) as caught:
                    generate_local(PROFILE, JOB, "template", None, str(path), "cpu", 100)
            self.assertNotIn(PROFILE, str(caught.exception))

    def test_local_cli_needs_no_api_key_and_never_calls_openai(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.model_directory(directory)
            root = Path(directory)
            (root / "profile.md").write_text(PROFILE)
            (root / "job.txt").write_text(JOB)
            with working_directory(root), patch.dict(os.environ, {"OPENAI_API_KEY": ""}), \
                    patch("personalized_cv.cli.generate_local", return_value=fixture()) as local, \
                    patch("personalized_cv.cli.generate") as openai:
                result = main(["--provider", "local", "--model", str(path),
                    "--profile", "profile.md", "--job", "job.txt", "--template",
                    str(ROOT / "cv-templates/01-reverse-chronological.md"), "--output", "local-cv"])
            self.assertEqual(result, 0)
            local.assert_called_once()
            openai.assert_not_called()
            self.assertTrue((root / "output/local-cv.pdf").is_file())
            self.assertIn("Provider: local", (root / "output/local-cv.report.md").read_text())

    def test_local_failure_never_falls_back_to_openai(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.model_directory(directory)
            root = Path(directory)
            (root / "profile.md").write_text(PROFILE)
            (root / "job.txt").write_text(JOB)
            with working_directory(root), patch("personalized_cv.cli.generate") as openai, \
                    patch("personalized_cv.cli.generate_local", side_effect=ProviderError("Local failure")):
                result = main(["--provider", "local", "--model", str(path),
                    "--profile", "profile.md", "--job", "job.txt", "--template",
                    str(ROOT / "cv-templates/01-reverse-chronological.md"), "--output", "failed"])
            self.assertEqual(result, 1)
            openai.assert_not_called()
            self.assertFalse((root / "output/failed.pdf").exists())


if __name__ == "__main__":
    unittest.main()
