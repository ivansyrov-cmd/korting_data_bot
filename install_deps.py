# -*- coding: utf-8 -*-
"""Bootstrap pip and install requirements on hosts without python3-pip."""
from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQ = ROOT / "requirements.txt"
PIP_PYZ_URL = "https://bootstrap.pypa.io/pip/pip.pyz"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
TMP = Path("/tmp") if Path("/tmp").is_dir() else Path.cwd()


def _run(cmd: list[str]) -> None:
    print("run:", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def _has_pip() -> bool:
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _bootstrap_pip() -> None:
    if _has_pip():
        return
    print("python has no pip, bootstrapping", flush=True)
    try:
        _run([sys.executable, "-m", "ensurepip", "--upgrade"])
        if _has_pip():
            return
    except Exception as exc:
        print(f"ensurepip failed: {exc}", flush=True)
    get_pip = TMP / "get-pip.py"
    try:
        print(f"download {GET_PIP_URL}", flush=True)
        urllib.request.urlretrieve(GET_PIP_URL, get_pip)
        _run([sys.executable, str(get_pip)])
        if _has_pip():
            return
    except Exception as exc:
        print(f"get-pip failed: {exc}", flush=True)
    try:
        _run(["apt-get", "update", "-qq"])
        _run(["apt-get", "install", "-y", "-qq", "python3-pip"])
    except Exception as exc:
        print(f"apt-get python3-pip failed: {exc}", flush=True)


def _pip_install(args: list[str]) -> None:
    if _has_pip():
        _run([sys.executable, "-m", "pip", *args])
        return
    pyz = TMP / "pip.pyz"
    print(f"download {PIP_PYZ_URL}", flush=True)
    urllib.request.urlretrieve(PIP_PYZ_URL, pyz)
    _run([sys.executable, str(pyz), *args])


def deps_ok() -> bool:
    try:
        import openpyxl  # noqa: F401
        import telegram  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_deps() -> None:
    if deps_ok():
        return
    if not REQ.is_file():
        raise SystemExit(f"missing {REQ}")
    print("installing python deps", flush=True)
    _bootstrap_pip()
    _pip_install(["install", "-r", str(REQ)])
    if not deps_ok():
        raise SystemExit(
            "python packages are still missing after install "
            "(need openpyxl and python-telegram-bot)"
        )


if __name__ == "__main__":
    ensure_deps()
