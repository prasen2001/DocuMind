from pathlib import Path

import pymupdf

from documind.extractor import _extract_text_regions, extract_pdf


def make_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 72), "Quarterly Results", fontsize=22)
    page.insert_text((72, 112), "Revenue increased to $4.2 million in October 2026.", fontsize=11)
    page.insert_text((72, 132), "The operating margin was 18 percent.", fontsize=11)
    document.save(path)
    document.close()


def test_extracts_text_layout_and_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "results.pdf"
    make_pdf(path)

    result = extract_pdf(path, document_id="a" * 32, filename="results.pdf")

    assert result["schema_version"] == "1.1"
    assert result["summary"]["page_count"] == 1
    assert result["summary"]["character_count"] > 50
    assert "Quarterly Results" in result["pages"][0]["text"]
    assert result["pages"][0]["regions"][0]["type"] == "title"
    assert len(result["pages"][0]["regions"][0]["bbox"]) == 4
    assert result["pages"][0]["needs_ocr"] is False
    assert result["summary"]["relationship_count"] >= 1


def test_rejects_password_protected_pdf(tmp_path: Path) -> None:
    source = pymupdf.open()
    source.new_page().insert_text((72, 72), "Secret")
    path = tmp_path / "protected.pdf"
    source.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader")
    source.close()

    try:
        extract_pdf(path, document_id="b" * 32, filename="protected.pdf")
    except ValueError as exc:
        assert "Password-protected" in str(exc)
    else:
        raise AssertionError("Encrypted input should be rejected")


def test_reconstructs_wrapped_bullets_across_pdf_blocks() -> None:
    def line(text: str, x0: float, y0: float, x1: float, *, size: float = 10, flags: int = 4):
        return {
            "bbox": [x0, y0, x1, y0 + 10],
            "spans": [{"text": text, "size": size, "flags": flags}],
        }

    page_dict = {
        "blocks": [
            {
                "type": 0,
                "lines": [line("Experience", 28, 250, 95, size=12, flags=20)],
            },
            {
                "type": 0,
                "lines": [
                    line("Insaito", 28, 269, 90, flags=20),
                    line("Remote", 540, 269, 583, flags=20),
                    line("Senior Software Engineer", 28, 283, 180, flags=6),
                    line("Sep 2025 – Aug 2026", 489, 283, 583, flags=6),
                    line("– Built an AI platform spanning frontend,", 30, 292, 400, flags=20),
                ],
            },
            {
                "type": 0,
                "lines": [
                    line("backend, workflows, and infrastructure.", 42, 305, 350),
                    line("– Added grounded document retrieval", 30, 315, 350, flags=20),
                ],
            },
            {
                "type": 0,
                "lines": [
                    line("with source citations.", 42, 327, 220),
                    line("Fold Health Inc.", 28, 342, 130, flags=20),
                    line("Pune, India", 520, 342, 583, flags=20),
                    line("Software Engineer", 28, 356, 140, flags=6),
                    line("Jul 2023 – Jun 2025", 492, 356, 583, flags=6),
                ],
            },
        ]
    }

    regions = _extract_text_regions(page_dict, 0, 792)

    assert [region["text"] for region in regions] == [
        "Experience",
        "Insaito | Remote Senior Software Engineer | Sep 2025 – Aug 2026",
        "– Built an AI platform spanning frontend, backend, workflows, and infrastructure.",
        "– Added grounded document retrieval with source citations.",
        "Fold Health Inc. | Pune, India Software Engineer | Jul 2023 – Jun 2025",
    ]
    assert [region["type"] for region in regions] == [
        "heading",
        "paragraph",
        "list",
        "list",
        "paragraph",
    ]
