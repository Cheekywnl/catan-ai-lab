"""Build a deterministic, self-contained browser package from the tested Python source."""

from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import sys
import networkx

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from engine import ENGINE_VERSION, RULESET

target = root / "dist/runtime"
target.mkdir(parents=True, exist_ok=True)
for name in [
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
]:
    shutil.copyfile(root / "node_modules/pyodide" / name, target / name)
files = {}
for path in (root / "engine").rglob("*"):
    if path.is_file() and (
        path.suffix in (".py", ".md", ".txt") or path.name == "LICENSE"
    ):
        files[path.relative_to(root).as_posix()] = path.read_bytes().replace(
            b"\r\n", b"\n"
        )
nx = Path(networkx.__file__).parent
for path in nx.rglob("*.py"):
    if "tests" not in path.parts:
        files["networkx/" + path.relative_to(nx).as_posix()] = (
            path.read_bytes().replace(b"\r\n", b"\n")
        )
license_path = next(nx.parent.glob("networkx-*.dist-info/licenses/LICENSE.txt"))
files["networkx/LICENSE.txt"] = license_path.read_bytes().replace(b"\r\n", b"\n")
archive = root / "dist/engine-source.zip"
with zipfile.ZipFile(
    archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
) as z:
    for name, content in sorted(files.items()):
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.create_system = 3  # Identical headers on Windows and Linux CI.
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        z.writestr(info, content)
metadata = {
    "engine_version": ENGINE_VERSION,
    "ruleset": RULESET,
    "upstream_revision": "ecf931181b9a65bb4116a2153fb78c16f1438e00",
    "networkx": networkx.__version__,
    "pyodide": json.loads((root / "node_modules/pyodide/package.json").read_text())[
        "version"
    ],
    "source_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
}
(root / "dist/engine-build.json").write_text(json.dumps(metadata, indent=2) + "\n")
for source, destination in [
    ("research/engine-validation.json", "dist/engine-validation.json"),
    ("research/implementation.md", "dist/implementation.md"),
    ("research/strength-v2.json", "dist/strength-v2.json"),
    ("research/solver-mathematics.md", "dist/solver-mathematics.md"),
    ("research/refinement-log.md", "dist/refinement-log.md"),
    ("research/strength-v3.json", "dist/strength-v3.json"),
    ("research/speed-v3.json", "dist/speed-v3.json"),
    ("research/strength-v3-original.json", "dist/strength-v3-original.json"),
    ("research/search-repair-v3.json", "dist/search-repair-v3.json"),
    ("research/development-history-v032.json", "dist/development-history-v032.json"),
    ("research/search12-v031-comparison.json", "dist/search12-v031-comparison.json"),
]:
    shutil.copyfile(root / source, root / destination)
print(
    f'Built {len(files)} source files; engine bundle {archive.stat().st_size:,} bytes; Pyodide {metadata["pyodide"]}.'
)
