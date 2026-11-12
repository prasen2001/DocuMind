from documind.relationships import infer_relationships


def test_links_caption_to_nearest_image_and_preserves_reading_order() -> None:
    regions = [
        {"id": "r1", "type": "paragraph", "text": "Overview", "bbox": [10, 10, 300, 30]},
        {
            "id": "r2",
            "type": "paragraph",
            "text": "Figure 1: Revenue by quarter",
            "bbox": [10, 210, 300, 230],
        },
    ]
    images = [{"id": "image-1", "bbox": [10, 50, 300, 200]}]

    relationships = infer_relationships(1, regions, images, [])

    assert relationships[0]["type"] == "precedes"
    assert relationships[1]["type"] == "caption_of"
    assert relationships[1]["target_id"] == "image-1"
    assert regions[1]["type"] == "caption"
