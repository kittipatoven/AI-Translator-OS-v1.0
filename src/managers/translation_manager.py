import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TranslationManager:
    """Offline NLLB-200 translation using a CTranslate2 model and tokenizer."""

    def __init__(self, model_dir: str, device: str = "cpu"):
        self.model_dir = Path(model_dir)
        self.device = device
        self._translator: Optional[object] = None
        self._tokenizer: Optional[object] = None
        self._load()

    def _load(self):
        try:
            import ctranslate2
            from tokenizers import Tokenizer

            required = [
                self.model_dir / "model.bin",
                self.model_dir / "tokenizer.json",
                self.model_dir / "config.json",
            ]
            for f in required:
                if not f.exists():
                    logger.error("Missing NLLB file: %s", f)
                    return

            logger.info("Loading NLLB model from %s", self.model_dir)
            self._translator = ctranslate2.Translator(
                str(self.model_dir),
                device=self.device,
                compute_type="int8",
                inter_threads=1,
                intra_threads=1,
            )
            self._tokenizer = Tokenizer.from_file(
                str(self.model_dir / "tokenizer.json")
            )
        except ImportError as exc:
            logger.error("NLLB runtime not available: %s", exc)
        except Exception as exc:
            logger.error("Failed to load NLLB model: %s", exc)

    def is_model_present(self) -> bool:
        return (
            self._translator is not None
            and self._tokenizer is not None
            and (self.model_dir / "model.bin").exists()
        )

    def translate(self, text: str, source: str, target: str) -> str:
        if not text:
            return ""
        if not self.is_model_present():
            raise RuntimeError(
                "NLLB model is not loaded. Run: python scripts/download_models.py --nllb"
            )

        src = self._tokenizer.encode(f"__{source}__ {text}", add_special_tokens=False)
        tgt = self._tokenizer.encode(f"__{target}__", add_special_tokens=False)
        results = self._translator.translate_batch(
            [src.tokens],
            target_prefix=[tgt.tokens],
            max_decoding_length=64,
            min_decoding_length=1,
            beam_size=1,
            no_repeat_ngram_size=2,
            repetition_penalty=1.2,
        )

        tokens = results[0].hypotheses[0]
        # Drop the forced target-prefix if the model repeated it.
        if tokens and tokens[: len(tgt.tokens)] == tgt.tokens:
            tokens = tokens[len(tgt.tokens) :]
        token_ids = [
            i for t in tokens for i in [self._tokenizer.token_to_id(t)] if i is not None
        ]
        output = self._tokenizer.decode(token_ids, skip_special_tokens=True)
        return output.strip()
