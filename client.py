import argparse
import base64
import json
import mimetypes
from pathlib import Path
import re
import time

import requests


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)


def encode_image(image_path: Path) -> dict[str, str]:
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    media_type, _ = mimetypes.guess_type(image_path.name)
    if media_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"Unsupported image type: {image_path.suffix or 'unknown'}")
    return {
        "data_base64": base64.b64encode(image_path.read_bytes()).decode("ascii"),
        "media_type": media_type,
    }


def _section(body: str, heading: str, next_headings: tuple[str, ...] = ()) -> str:
    stop = "|".join(re.escape(f"# {item}") for item in next_headings)
    tail = rf"(?=\n(?:{stop})\s*\n|\Z)" if stop else r"\Z"
    match = re.search(rf"(?m)^# {re.escape(heading)}\s*\n(?P<value>.*?){tail}", body, re.DOTALL)
    return match.group("value").strip() if match else ""


def parse_payload(file_path: str) -> dict:
    path = Path(file_path).resolve()
    raw_data = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw_data)
    metadata = match.group("meta") if match else ""
    body = match.group("body") if match else raw_data

    def metadata_value(key: str, default: str) -> str:
        item = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", metadata)
        return item.group(1).strip() if item else default

    student_id = metadata_value("student_id", "default_student")
    task_type = metadata_value("task_type", "task_1").lower()
    if task_type not in {"task_1", "task_2"}:
        raise ValueError("task_type must be task_1 or task_2")

    prompt_text = _section(body, "Prompt Text", ("Prompt Image", "Essay Text"))
    essay_text = _section(body, "Essay Text")
    if not essay_text:
        raise ValueError("Missing or empty '# Essay Text' section")

    images = []
    image_section = _section(body, "Prompt Image", ("Essay Text",))
    for filename in re.findall(r"!\[\[(.*?)\]\]", image_section):
        images.append(encode_image(path.parent / filename.strip()))

    return {
        "student_id": student_id,
        "task_type": task_type,
        "essay_text": f"TASK PROMPT:\n{prompt_text}\n\nSTUDENT ESSAY:\n{essay_text}",
        "images": images,
    }


def transmit_payload(file_path: str, url: str) -> None:
    payload = parse_payload(file_path)
    start_time = time.monotonic()
    response = requests.post(url, json=payload, timeout=120)
    elapsed = time.monotonic() - start_time
    print(f"Latency: {elapsed:.2f}s")
    print(f"HTTP status: {response.status_code}")
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IELTS evaluation client")
    parser.add_argument("-i", "--input", required=True, help="Input Markdown file")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/evaluate")
    args = parser.parse_args()
    transmit_payload(args.input, args.url)
