from pathlib import Path

import pymupdf

from documind.assets import extract_image_asset
from documind.extractor import extract_pdf

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8ffff3f0005fe02fea73581480000000049454e44ae426082"
)


def test_extracts_original_embedded_image_asset(tmp_path: Path) -> None:
    path = tmp_path / "image.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    page.insert_image((50, 60, 250, 260), stream=PNG_1X1)
    document.save(path)
    document.close()
    extracted = extract_pdf(path, document_id="e" * 32, filename="image.pdf")
    image = extracted["pages"][0]["images"][0]

    payload, content_type = extract_image_asset(path, page_number=1, image=image)

    assert image["xref"] > 0
    assert payload.startswith(b"\x89PNG")
    assert content_type == "image/png"
