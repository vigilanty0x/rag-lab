"""Small offline source and public-boundary check used by CI."""

from pathlib import Path
import json
import py_compile


ROOT = Path(__file__).resolve().parents[1]
forbidden = [
    " ".join(("private", "repo", "name")),
    " ".join(("client", "secret")),
    "_".join(("api", "key")) + "=",
    " ".join(("BEGIN", "PRIVATE", "KEY")),
]
checked = 0
for path in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "tests").rglob("*.py")):
    py_compile.compile(str(path), doraise=True)
    checked += 1
for path in [ROOT / "examples" / "suite.json"]:
    json.loads(path.read_text(encoding="utf-8"))
for path in [item for item in ROOT.rglob("*") if item.is_file() and ".git" not in item.parts]:
    if path.suffix.lower() not in {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt"}:
        continue
    lowered = path.read_text(encoding="utf-8").lower()
    for marker in forbidden:
        if marker.lower() in lowered:
            raise SystemExit(f"public-boundary marker found in {path.relative_to(ROOT)}")
print(f"checked {checked} Python files and public fixtures")
