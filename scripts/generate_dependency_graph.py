"""Generate a Markdown dependency graph of the project."""
import ast
import json
from pathlib import Path


def build_graph(root: Path):
    data = {}
    for f in sorted(root.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        imports = []
        classes = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)

        rel = f.relative_to(root).as_posix()
        data[rel] = {
            "classes": classes,
            "imports": sorted(set(imports)),
        }
    return data


def render_markdown(data: dict, output: Path):
    lines = ["# AI Translator OS v1.0 — Dependency Graph\n"]
    lines.append("## Per-File Imports and Classes\n\n")
    for f in sorted(data):
        info = data[f]
        lines.append(f"### {f}\n")
        lines.append(f"- Classes: {', '.join(info['classes']) or '-'}\n")
        lines.append("- Imports:\n")
        for imp in info["imports"]:
            lines.append(f"  - `{imp}`\n")
        lines.append("\n")

    lines.append("## Call Graph Summary\n\n")
    lines.append("```\n")
    lines.append("main.py\n")
    lines.append("├── managers/config_manager.py\n")
    lines.append("├── managers/lcd_manager.py\n")
    lines.append("├── managers/button_manager.py\n")
    lines.append("├── managers/audio_manager.py\n")
    lines.append("├── managers/speech_manager.py\n")
    lines.append("├── managers/translation_manager.py\n")
    lines.append("├── managers/tts_manager.py\n")
    lines.append("├── managers/conversation_manager.py\n")
    lines.append("├── managers/dictionary_manager.py\n")
    lines.append("├── managers/rule_engine.py\n")
    lines.append("├── managers/back_translation_manager.py\n")
    lines.append("├── managers/confidence_manager.py\n")
    lines.append("├── managers/history_manager.py\n")
    lines.append("├── managers/language_pack_manager.py\n")
    lines.append("├── managers/resource_manager.py\n")
    lines.append("├── managers/logging_manager.py\n")
    lines.append("├── managers/watchdog_manager.py\n")
    lines.append("└── utils/*\n")
    lines.append("```\n")

    output.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    graph = build_graph(project_root)
    out = project_root / "docs" / "DEPENDENCY_GRAPH.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_markdown(graph, out)
    print(f"Dependency graph written to {out}")
