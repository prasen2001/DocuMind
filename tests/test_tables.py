from documind.tables import extract_ocr_tables


def test_reconstructs_scanned_table_from_lines_and_ocr_words() -> None:
    preprocessing = {
        "vertical_lines": [[10, 10, 11, 110], [60, 10, 61, 110], [110, 10, 111, 110]],
        "horizontal_lines": [[10, 10, 110, 11], [10, 60, 110, 61], [10, 110, 110, 111]],
    }
    regions = [
        {
            "words": [
                {"text": "Name", "bbox": [20, 20, 45, 35]},
                {"text": "Value", "bbox": [70, 20, 100, 35]},
                {"text": "Revenue", "bbox": [15, 70, 50, 85]},
                {"text": "$4.2M", "bbox": [72, 70, 100, 85]},
            ]
        }
    ]

    tables = extract_ocr_tables(1, regions, preprocessing)

    assert tables[0]["method"] == "opencv-grid-tesseract"
    assert tables[0]["rows"] == [["Name", "Value"], ["Revenue", "$4.2M"]]
    assert tables[0]["row_count"] == 2
    assert tables[0]["column_count"] == 2
    assert tables[0]["bbox"] == [10.5, 10.5, 110.5, 110.5]
