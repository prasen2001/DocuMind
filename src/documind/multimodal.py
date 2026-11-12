from __future__ import annotations

import importlib.util
import os
import threading
from typing import Any, Protocol

DEFAULT_MODEL = "microsoft/Florence-2-base"
TASKS = {
    "caption": "<DETAILED_CAPTION>",
    "objects": "<OD>",
    "regions": "<DENSE_REGION_CAPTION>",
}


class MultimodalUnavailable(RuntimeError):
    pass


class ImageAnalyzer(Protocol):
    def analyze(
        self, image_bytes: bytes, task_prompt: str
    ) -> tuple[dict[str, Any], tuple[int, int]]: ...


def multimodal_available() -> bool:
    return (
        os.environ.get("DOCUMIND_ENABLE_MULTIMODAL", "0") == "1"
        and importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("transformers") is not None
        and importlib.util.find_spec("cv2") is not None
    )


class FlorenceAnalyzer:
    """Lazy Microsoft Florence-2 adapter using its prompt-based visual tasks."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        if not multimodal_available():
            raise MultimodalUnavailable(
                "Multimodal analysis requires the multimodal extra and DOCUMIND_ENABLE_MULTIMODAL=1"
            )
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        allow_model_code = os.environ.get("DOCUMIND_ALLOW_MODEL_CODE", "0") == "1"
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(
            model_name, trust_remote_code=allow_model_code
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, trust_remote_code=allow_model_code
        )
        self.model.eval()

    def analyze(
        self, image_bytes: bytes, task_prompt: str
    ) -> tuple[dict[str, Any], tuple[int, int]]:
        import cv2  # type: ignore[import-not-found]
        import numpy as np

        encoded = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("The extracted image could not be decoded")
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width = image.shape[:2]
        inputs = self.processor(text=task_prompt, images=image, return_tensors="pt")
        with self.torch.no_grad():
            generated = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=512,
                num_beams=3,
                do_sample=False,
            )
        generated_text = self.processor.batch_decode(generated, skip_special_tokens=False)[0]
        result = self.processor.post_process_generation(
            generated_text, task=task_prompt, image_size=(width, height)
        )
        return result, (width, height)


_analyzer: FlorenceAnalyzer | None = None
_analyzer_lock = threading.Lock()


def default_analyzer() -> FlorenceAnalyzer:
    global _analyzer
    with _analyzer_lock:
        if _analyzer is None:
            _analyzer = FlorenceAnalyzer(os.environ.get("DOCUMIND_MULTIMODAL_MODEL", DEFAULT_MODEL))
        return _analyzer


def analyze_image(
    image_bytes: bytes,
    image: dict[str, Any],
    *,
    task: str = "caption",
    analyzer: ImageAnalyzer | None = None,
) -> dict[str, Any]:
    if task not in TASKS:
        raise ValueError(f"Unsupported visual task: {task}")
    selected = analyzer or default_analyzer()
    raw, (pixel_width, pixel_height) = selected.analyze(image_bytes, TASKS[task])
    task_result = raw.get(TASKS[task], raw)
    pdf_box = image["bbox"]
    grounded: list[dict[str, Any]] = []
    if isinstance(task_result, dict):
        boxes = task_result.get("bboxes", [])
        labels = task_result.get("labels", [])
        for index, box in enumerate(boxes):
            if len(box) != 4 or not pixel_width or not pixel_height:
                continue
            x0, y0, x1, y1 = box
            grounded.append(
                {
                    "label": labels[index] if index < len(labels) else "",
                    "bbox": [
                        round(pdf_box[0] + x0 / pixel_width * (pdf_box[2] - pdf_box[0]), 2),
                        round(pdf_box[1] + y0 / pixel_height * (pdf_box[3] - pdf_box[1]), 2),
                        round(pdf_box[0] + x1 / pixel_width * (pdf_box[2] - pdf_box[0]), 2),
                        round(pdf_box[1] + y1 / pixel_height * (pdf_box[3] - pdf_box[1]), 2),
                    ],
                }
            )
    caption = task_result if isinstance(task_result, str) else task_result.get("caption", "")
    return {
        "task": task,
        "model": os.environ.get("DOCUMIND_MULTIMODAL_MODEL", DEFAULT_MODEL),
        "method": "florence-2-visual-grounding",
        "caption": caption,
        "objects": grounded,
        "source": {"image_id": image["id"], "bbox": pdf_box},
        "notice": "Model-derived visual claims require source review.",
    }
