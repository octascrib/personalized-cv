"""Optional real-runtime smoke test; no pretrained model or network is used."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personalized_cv.llm import ProviderError
from personalized_cv.local_llm import generate_local, parse_local_response

HAS_LOCAL_RUNTIME = all(importlib.util.find_spec(name) is not None
                        for name in ("torch", "transformers", "safetensors"))


@unittest.skipUnless(HAS_LOCAL_RUNTIME, "Install the local extra to run the real safetensors smoke test")
class LocalRuntimeTests(unittest.TestCase):
    def test_real_safetensors_loading_tokenization_and_generation(self):
        import torch
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

        original_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                raw = Tokenizer(WordLevel({"[UNK]": 0, "[PAD]": 1, "[EOS]": 2, "hello": 3}, unk_token="[UNK]"))
                raw.pre_tokenizer = Whitespace()
                tokenizer = PreTrainedTokenizerFast(tokenizer_object=raw, unk_token="[UNK]",
                    pad_token="[PAD]", eos_token="[EOS]", model_max_length=16384)
                tokenizer.chat_template = "{% for message in messages %}{{ message['role'] + ': ' + message['content'] + '\n' }}{% endfor %}{% if add_generation_prompt %}assistant: {% endif %}"
                tokenizer.save_pretrained(path)
                model = GPT2LMHeadModel(GPT2Config(vocab_size=4, n_positions=16384, n_ctx=16384,
                    n_embd=8, n_layer=1, n_head=1, bos_token_id=2, eos_token_id=2, pad_token_id=1))
                model.save_pretrained(path, safe_serialization=True)
                self.assertTrue((path / "model.safetensors").is_file())
                del model
                # A randomly initialized four-token model cannot produce CV JSON.
                # Reaching schema rejection proves real loading and inference ran.
                with patch("personalized_cv.local_llm.parse_local_response", wraps=parse_local_response) as parse:
                    with self.assertRaisesRegex(ProviderError, "invalid CV JSON"):
                        generate_local("Name: Test Candidate", "Example job", "Use a brief CV.",
                                       None, str(path), "cpu", 2)
                    parse.assert_called_once()
        finally:
            torch.set_num_threads(original_threads)


if __name__ == "__main__":
    unittest.main()
