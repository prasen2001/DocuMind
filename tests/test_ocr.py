from pathlib import Path

import pymupdf

from documind import extractor

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8ffff3f0005fe02fea73581480000000049454e44ae426082"
)


def test_applies_ocr_to_scanned_page(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "scan.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    page.insert_image(page.rect, stream=PNG_1X1)
    document.save(path)
    document.close()

    monkeypatch.setattr(extractor, "ocr_available", lambda: True)
    monkeypatch.setattr(
        extractor,
        "extract_ocr_regions",
        lambda page: [
            {
                "type": "ocr_text",
                "bbox": [20, 30, 250, 50],
                "text": "Recognized scanned evidence",
                "font_size": 0,
                "confidence": 94.5,
                "source": "tesseract",
            }
        ],
    )

    result = extractor.extract_pdf(path, document_id="c" * 32, filename="scan.pdf")

    assert result["summary"]["ocr_pages"] == 1
    assert result["summary"]["ocr_required_pages"] == 0
    assert result["pages"][0]["ocr_applied"] is True
    assert result["pages"][0]["text"] == "Recognized scanned evidence"
    assert result["pages"][0]["regions"][-1]["confidence"] == 94.5
