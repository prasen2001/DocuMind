from pathlib import Path

import pymupdf

from documind.extractor import extract_pdf


def make_chart_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page(width=500, height=500)
    page.insert_text((70, 55), "Quarterly Revenue Growth", fontsize=16)
    page.draw_line((80, 350), (420, 350), width=1)
    page.draw_line((80, 350), (80, 100), width=1)
    for index, (label, value, height) in enumerate(
        [("Q1 10", "10", 70), ("Q2 20", "20", 130), ("Q3 30", "30", 200)]
    ):
        x = 120 + index * 90
        page.draw_rect((x, 350 - height, x + 42, 350), color=(0.1, 0.4, 0.3), fill=(0.2, 0.6, 0.4))
        page.insert_text((x, 375), label, fontsize=9)
        page.insert_text((x + 12, 340 - height), value, fontsize=9)
    document.save(path)
    document.close()


def test_extracts_vector_chart_values_and_evidence(tmp_path: Path) -> None:
    path = tmp_path / "chart.pdf"
    make_chart_pdf(path)

    result = extract_pdf(path, document_id="d" * 32, filename="chart.pdf")

    assert result["summary"]["chart_count"] == 1
    chart = result["pages"][0]["charts"][0]
    assert chart["type"] == "bar"
    assert chart["title"] == "Quarterly Revenue Growth"
    assert {value["raw"] for value in chart["values"]} >= {"10", "20", "30"}
    assert all(len(value["bbox"]) == 4 for value in chart["values"])
    chart_regions = [
        region for region in result["pages"][0]["regions"] if region["type"] == "chart"
    ]
    assert chart_regions[0]["chart_id"] == chart["id"]
