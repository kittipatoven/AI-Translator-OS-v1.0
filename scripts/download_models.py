"""Download offline models for AI Translator OS.

Run on a computer with internet, then copy the `models/` folder to the Pi.

Example:
    python scripts/download_models.py --all --output models

Requires:
    pip install huggingface_hub
"""
import argparse
import os
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download, snapshot_download
except ImportError:
    raise SystemExit("Please install huggingface_hub: pip install huggingface_hub")

WHISPER_MODELS = {
    "tiny-q5_1": "ggml-tiny-q5_1.bin",
    "tiny": "ggml-tiny.bin",
    "base-q5_1": "ggml-base-q5_1.bin",
    "base": "ggml-base.bin",
    "small-q5_1": "ggml-small-q5_1.bin",
    "small": "ggml-small.bin",
}

NLLB_MODELS = {
    "600m": "mijuanlo/nllb-200-distilled-600M-ct2-int8",
    "1.3b": "mijuanlo/nllb-200-distilled-1.3B-int8-ct2",
    "3.3b": "mijuanlo/nllb-200-3.3B-ct2-int8",
}


def _download_whisper(variant, output_dir):
    filename = WHISPER_MODELS[variant]
    local_dir = Path(output_dir) / "whisper"
    local_dir.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id="ggerganov/whisper.cpp",
        filename=filename,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
    )
    print(f"[OK] Whisper: {filename} -> {local_dir / filename}")


def _download_nllb(variant, output_dir):
    repo_id = NLLB_MODELS[variant]
    local_dir = Path(output_dir) / "nllb"
    local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
        allow_patterns=["model.bin", "*.json", "*.txt"],
    )
    print(f"[OK] NLLB: {repo_id} -> {local_dir}")


def _download_piper(voice, output_dir):
    # voice example: en_US-lessac-low
    parts = voice.split("-")
    if len(parts) != 3:
        raise SystemExit("Voice must be in the form {lang}_{COUNTRY}-{speaker}-{quality}, e.g. en_US-lessac-low")
    lang_country, speaker, quality = parts
    lang = lang_country.split("_")[0]
    base_path = f"{lang}/{lang_country}/{speaker}/{quality}/{voice}"
    local_dir = Path(output_dir) / "piper"
    local_dir.mkdir(parents=True, exist_ok=True)
    for ext in [".onnx", ".onnx.json"]:
        hf_hub_download(
            repo_id="rhasspy/piper-voices",
            filename=base_path + ext,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
        )
    print(f"[OK] Piper voice: {voice} -> {local_dir / base_path}.onnx")


def main():
    parser = argparse.ArgumentParser(description="Download offline translation models")
    parser.add_argument("--all", action="store_true", help="download recommended default set")
    parser.add_argument("--whisper", choices=list(WHISPER_MODELS.keys()), help="whisper model variant")
    parser.add_argument("--nllb", choices=list(NLLB_MODELS.keys()), help="nllb model variant")
    parser.add_argument("--voice", help="piper voice key, e.g. en_US-lessac-low")
    parser.add_argument("--output", default="models", help="output directory")
    args = parser.parse_args()

    if args.all:
        args.whisper = args.whisper or "base-q5_1"
        args.nllb = args.nllb or "600m"
        args.voice = args.voice or "en_US-lessac-low"

    if not (args.whisper or args.nllb or args.voice):
        parser.print_help()
        return

    if args.whisper:
        _download_whisper(args.whisper, args.output)
    if args.nllb:
        _download_nllb(args.nllb, args.output)
    if args.voice:
        _download_piper(args.voice, args.output)

    print(f"\nModels saved to: {Path(args.output).resolve()}")
    print("Copy this folder to the Raspberry Pi before building the Docker image.")


if __name__ == "__main__":
    main()
