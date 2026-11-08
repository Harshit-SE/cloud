"""
AeroParse Submission Packager
Creates the final 230101065.zip submission archive matching the assignment structure.
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLL_NUMBER = "230101065"
ZIP_PATH = ROOT / f"{ROLL_NUMBER}.zip"
REFLECTION_PDF = ROOT / f"{ROLL_NUMBER}.pdf"
REPORT_PDF = ROOT / "report" / "report.pdf"

INCLUDE_DIRS = [
    "cluster",
    "data",
    "datasets",
    "k8s",
    "models",
    "network",
    "prompts",
    "report",
    "results",
    "scripts",
    "service",
    "tests",
    "tools",
    "training",
    "worker",
    ".github",
]

INCLUDE_FILES = [
    "AI_USE.md",
    "Makefile",
    "README.md",
    ".gitignore",
]

EXCLUDE_EXTS = {".pyc", ".tar.gz", ".zip", ".log"}
EXCLUDE_DIRS = {"__pycache__", ".venv", ".venv-deploy", ".ruff_cache", "output"}


def package():
    print(f"=== AeroParse Packager for Roll Number: {ROLL_NUMBER} ===")

    if not REPORT_PDF.is_file():
        print(f"[-] ERROR: Missing {REPORT_PDF}!")
        sys.exit(1)
    print(f"[+] Found Report: {REPORT_PDF}")

    has_reflection = REFLECTION_PDF.is_file()
    if not has_reflection:
        print(f"[!] Warning: {REFLECTION_PDF} not found in workspace yet.")
        print(f"    Please handwrite the reflection notes, scan to {ROLL_NUMBER}.pdf, and place it in the project root.")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Include top-level files
        for fname in INCLUDE_FILES:
            fpath = ROOT / fname
            if fpath.is_file():
                zipf.write(fpath, arcname=fname)
                print(f"  + Added: {fname}")

        # Include reflection PDF if present
        if has_reflection:
            zipf.write(REFLECTION_PDF, arcname=f"{ROLL_NUMBER}.pdf")
            print(f"  + Added: {ROLL_NUMBER}.pdf (Handwritten Reflection Notes)")

        # Include directories
        for dname in INCLUDE_DIRS:
            dpath = ROOT / dname
            if not dpath.is_dir():
                continue
            for file_path in dpath.rglob("*"):
                if file_path.is_file():
                    # Check exclusions
                    if file_path.suffix in EXCLUDE_EXTS:
                        continue
                    if any(part in EXCLUDE_DIRS for part in file_path.parts):
                        continue
                    arcname = str(file_path.relative_to(ROOT)).replace("\\", "/")
                    zipf.write(file_path, arcname=arcname)

    print(f"[SUCCESS] Packaged submission archive: {ZIP_PATH}")
    print(f"Archive Size: {ZIP_PATH.stat().st_size / (1024*1024):.2f} MB")


if __name__ == "__main__":
    package()
