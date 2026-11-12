from documind.multimodal import analyze_image


class FakeFlorence:
    def analyze(self, image_bytes: bytes, task_prompt: str) -> tuple[dict, tuple[int, int]]:
        assert image_bytes == b"image"
        return {
            task_prompt: {
                "bboxes": [[10, 20, 60, 80]],
                "labels": ["revenue bar"],
            }
        }, (100, 100)


def test_maps_visual_grounding_back_to_pdf_coordinates() -> None:
    image = {"id": "image-1", "bbox": [100, 200, 300, 500]}

    result = analyze_image(b"image", image, task="objects", analyzer=FakeFlorence())

    assert result["objects"] == [{"label": "revenue bar", "bbox": [120.0, 260.0, 220.0, 440.0]}]
    assert result["source"] == {"image_id": "image-1", "bbox": [100, 200, 300, 500]}
    assert result["notice"].startswith("Model-derived")
