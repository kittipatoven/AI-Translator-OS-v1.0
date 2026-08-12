"""Download offline models for AI Translator OS without pip/huggingface_hub.

Uses only the Python standard library so it can run on a PC where pip is blocked.

Usage:
    python scripts/download_models_offline.py --dry-run
    python scripts/download_models_offline.py
"""
import argparse
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

# Allow self-signed certs / older systems if needed
ssl._create_default_https_context = ssl._create_unverified_context

BASE_URL = "https://huggingface.co"

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
    "1.3b": "mijuanlo/nllb-200-distilled-1.3B-ct2-int8",
    "3.3b": "mijuanlo/nllb-200-3.3B-ct2-int8",
}

PIPER_REPO = "rhasspy/piper-voices"


def _request(url: str, retries: int = 3) -> bytes:
    """Fetch raw bytes from a URL with retries."""
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Translator-OS/1.0"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code == 404:
                raise
            time.sleep(2 ** attempt)
        except Exception as exc:
            last_err = exc
            time.sleep(2 ** attempt)
    raise last_err


def _fetch_json(url: str) -> dict | list:
    return json.loads(_request(url).decode("utf-8"))


def _file_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "AI-Translator-OS/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.headers.get("Content-Length", 0))
    except Exception:
        return 0


def _download_file(url: str, dest: Path, dry_run: bool = False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    size_on_remote = _file_size(url)
    if dest.exists():
        if size_on_remote and dest.stat().st_size == size_on_remote:
            print(f"  [skip] {dest} (already complete)")
            return
        else:
            print(f"  [resume] {dest} (existing {dest.stat().st_size} / {size_on_remote})")
    else:
        print(f"  [download] {dest} ({size_on_remote} bytes)")

    if dry_run:
        return

    req = urllib.request.Request(url, headers={"User-Agent": "AI-Translator-OS/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(8192)
            if not chunk:
                break
            f.write(chunk)
    print(f"  [ok] {dest}")


def _download_whisper(variant: str, model_dir: Path, dry_run: bool = False):
    filename = WHISPER_MODELS[variant]
    url = f"{BASE_URL}/ggerganov/whisper.cpp/resolve/main/{filename}"
    dest = model_dir / "whisper" / filename
    _download_file(url, dest, dry_run=dry_run)


def _download_nllb(variant: str, model_dir: Path, dry_run: bool = False):
    repo_id = NLLB_MODELS[variant]
    tree_url = f"{BASE_URL}/api/models/{repo_id}/tree/main?recursive=true"
    print(f"Listing NLLB files: {repo_id}")
    try:
        tree = _fetch_json(tree_url)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Cannot list repo {repo_id}: {exc}")

    for item in tree:
        if item.get("type") != "file":
            continue
        path = item["path"]
        url = f"{BASE_URL}/{repo_id}/resolve/main/{path}"
        dest = model_dir / "nllb" / path
        _download_file(url, dest, dry_run=dry_run)


def _piper_base_path(voice: str) -> str:
    parts = voice.split("-")
    if len(parts) != 3:
        raise ValueError(f"Invalid Piper voice key: {voice}")
    lang_country, speaker, quality = parts
    lang = lang_country.split("_")[0]
    return f"{lang}/{lang_country}/{speaker}/{quality}/{voice}"


def _download_piper_voices(model_dir: Path, packs_dir: Path | None = None, dry_run: bool = False):
    if packs_dir is None:
        packs_dir = Path(__file__).resolve().parent.parent / "data" / "language_packs"

    voices = set()
    for f in packs_dir.glob("*.json"):
        try:
            pack = json.loads(f.read_text(encoding="utf-8"))
            voice = pack.get("piper_voice")
            if voice:
                voices.add(voice)
        except Exception:
            continue

    # Fallback defaults
    voices.update({"en_US-lessac-low", "zh_CN-huayan-x_low"})

    if not voices:
        print("No Piper voices configured.")
        return

    for voice in sorted(voices):
        base = _piper_base_path(voice)
        for ext in (".onnx", ".onnx.json"):
            url = f"{BASE_URL}/{PIPER_REPO}/resolve/main/{base}{ext}"
            dest = model_dir / "piper" / base
            _download_file(url, dest / (voice + ext), dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="Download offline models without pip")
    parser.add_argument(
        "--output",
        default="models",
        help="Output directory for models (default: models)",
    )
    parser.add_argument(
        "--whisper",
        choices=list(WHISPER_MODELS.keys()),
        default="base-q5_1",
        help="Whisper model variant",
    )
    parser.add_argument(
        "--nllb",
        choices=list(NLLB_MODELS.keys()),
        default="600m",
        help="NLLB model variant",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without writing files",
    )
    args = parser.parse_args()

    model_dir = Path(args.output)
    model_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("AI Translator OS — Offline model downloader")
    print("Mode:", "dry-run" if args.dry_run else "download")
    print("Output:", model_dir)
    print("=" * 50)

    _download_whisper(args.whisper, model_dir, dry_run=args.dry_run)
    _download_nllb(args.nllb, model_dir, dry_run=args.dry_run)
    _download_piper_voices(model_dir, dry_run=args.dry_run)

    if args.dry_run:
        print("\nDry-run complete. Run without --dry-run to download.")
    else:
        print("\nAll downloads complete.")


if __name__ == "__main__":
    main()
