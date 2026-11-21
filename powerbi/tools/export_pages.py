"""Turn Power BI Desktop page screenshots into README figures and a PDF of the whole report.

    powerbi-report-author preview powerbi/FloodIt.Report --host desktop --screenshot <dir> --all-pages --scale 2
    python powerbi/tools/export_pages.py <dir>

Crops each capture to the 16:9 report canvas (drops the Desktop chrome and the Filters pane),
writes figures/powerbi_NN_<page>.png for the pages shown in the README and
reports/FloodIt_PowerBI_report.pdf with every page in report order.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PAGES = [  # (capture file name written by the CLI, figure slug or None)
    ("Overview", "01_overview"), ("Growth", None), ("Retention", "03_retention"),
    ("Revenue & LTV", "04_revenue_ltv"), ("Levels & difficulty", "05_levels"), ("Player segments", "06_segments"),
    ("Churn model", "07_churn_model"), ("A_B_ observational tests and test design", None),
    ("What it's worth", "09_impact"), ("Data limitations", None),
]
CANVAS = (0, 62, 2632, 1542)  # report canvas inside a 3034 x 1604 Desktop capture


def main(src: Path) -> None:
    pages = []
    for name, slug in PAGES:
        im = Image.open(src / f"{name}.png").convert("RGB")
        assert im.size == (3034, 1604), f"{name}: unexpected capture size {im.size}"
        page = im.crop(CANVAS)
        pages.append(page)
        if slug:
            fig = page.resize((1600, round(1600 * page.height / page.width)), Image.LANCZOS)
            fig.save(ROOT / "figures" / f"powerbi_{slug}.png", optimize=True)
    pages[0].save(ROOT / "reports" / "FloodIt_PowerBI_report.pdf", save_all=True, append_images=pages[1:], resolution=150.0)
    print(f"{len(pages)} pages -> reports/FloodIt_PowerBI_report.pdf")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
