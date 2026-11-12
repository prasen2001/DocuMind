from pathlib import Path

import pymupdf

from documind.extractor import extract_pdf


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
