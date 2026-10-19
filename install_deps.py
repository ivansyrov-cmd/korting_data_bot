# -*- coding: utf-8 -*-
"""Install vendored wheels without system pip (Alpine PEP 668 safe)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQ = ROOT / "requirements.txt"
PIP_PYZ = ROOT / "vendor" / "pip.pyz"
WHEELS = ROOT / "vendor" / "wheels"


def _run(cmd: list[str]) -> None:
    print("run:", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env["PIP_BREAK_SYSTEM_PACKAGES"] = "1"
    subprocess.check_call(cmd, env=env)


def _writable_dir() -> Path:
    for folder in (
        Path("/tmp/korting-pkgs"),
        Path(tempfile.gettempdir()) / "korting-pkgs",
        ROOT / ".deps",
    ):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return folder
        except OSError:
            continue
    return ROOT / ".deps"


def _use_path(folder: Path) -> None:
    text = str(folder)
    if text not in sys.path:
        sys.path.insert(0, text)


def deps_ok() -> bool:
    try:
        import openpyxl  # noqa: F401
        import telegram  # noqa: F401
        return True
    except ImportError:
        return False


def _unpack_wheels(target: Path) -> None:
    wheels = sorted(WHEELS.glob("*.whl")) if WHEELS.is_dir() else []
    if not wheels:
        raise FileNotFoundError(f"no wheels in {WHEELS}")
    print(f"unpacking {len(wheels)} wheels into {target}", flush=True)
    for whl in wheels:
        print(f"unpack {whl.name}", flush=True)
        with zipfile.ZipFile(whl) as zf:
            zf.extractall(target)


def _pip_target_install(target: Path) -> None:
    cmd = [
        sys.executable,
        str(PIP_PYZ),
        "install",
        "--upgrade",
        "--target",
        str(target),
        "--break-system-packages",
    ]
    if WHEELS.is_dir() and any(WHEELS.glob("*.whl")):
        cmd += ["--no-index", "--find-links", str(WHEELS)]
    cmd += ["-r", str(REQ)]
    _run(cmd)


def ensure_deps() -> None:
    target = _writable_dir()
    _use_path(target)
    if deps_ok():
        return
    print(f"installing python deps into {target}", flush=True)
    try:
        _unpack_wheels(target)
    except Exception as exc:
        print(f"wheel unpack failed: {exc}", flush=True)
        if not PIP_PYZ.is_file():
            raise SystemExit(f"missing bundled pip: {PIP_PYZ}")
        _pip_target_install(target)
    _use_path(target)
    if not deps_ok():
        raise SystemExit(
            "python packages are still missing after install "
            "(need openpyxl and python-telegram-bot)"
        )


if __name__ == "__main__":
    ensure_deps()
