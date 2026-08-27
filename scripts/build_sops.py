"""Build the six Quote Generator SOP PDFs into sops/."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sop_docs import all_sops  # noqa: E402
from sop_layout import write_pdf  # noqa: E402


def main() -> None:
    out_dir = ROOT / "sops"
    out_dir.mkdir(exist_ok=True)
    for filename, doc in all_sops():
        path = out_dir / filename
        write_pdf(str(path), doc)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
