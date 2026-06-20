"""Build the submission Word document (cover page + full portfolio) from docs/PORTFOLIO.md.

Uses the bundled pandoc (pypandoc_binary). Inserts a Word page break after the title/team block so
it becomes a standalone cover page. Screenshots are embedded (run with cwd=docs so assets/* resolve).
"""

from __future__ import annotations

import os
from pathlib import Path

import pypandoc

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "PORTFOLIO.md"
MARKER = "> This single document is the comprehensive portfolio"
PAGEBREAK = '\n\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n'


def main() -> None:
    md = SRC.read_text(encoding="utf-8")
    if MARKER in md:
        md = md.replace(MARKER, PAGEBREAK + MARKER, 1)

    out = ROOT / "ClinicalBridge_Portfolio.docx"
    try:
        if out.exists():
            out.unlink()  # raises if the file is locked (open in Word)
    except PermissionError:
        out = ROOT / "ClinicalBridge_Portfolio_new.docx"
        print(f"[!] Existing .docx is locked (open in Word?) — writing to {out.name} instead.")

    tmp = ROOT / "docs" / "_cover_tmp.md"
    tmp.write_text(md, encoding="utf-8")
    cwd = os.getcwd()
    try:
        os.chdir(ROOT / "docs")  # so relative image paths (assets/*.png) embed
        pypandoc.convert_file("_cover_tmp.md", "docx", outputfile=str(out), extra_args=["--standalone"])
    finally:
        os.chdir(cwd)
        tmp.unlink(missing_ok=True)

    print(f"[OK] {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
