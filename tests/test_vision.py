import pymupdf

from documind.vision import preprocess_page, vision_available


def test_preprocesses_page_and_detects_structural_lines() -> None:
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    for x in (50, 150, 250):
        page.draw_line((x, 100), (x, 300), width=2)
    for y in (100, 200, 300):
        page.draw_line((50, y), (250, y), width=2)

    result = preprocess_page(page)
    document.close()

    assert vision_available() is True
    assert result is not None
    assert result["image"].startswith(b"\x89PNG")
    assert result["steps"] == [
        "grayscale",
        "adaptive-threshold",
        "deskew",
        "line-morphology",
    ]
    assert result["structure_boxes"]
    assert len(result["structure_boxes"][0]) == 4
