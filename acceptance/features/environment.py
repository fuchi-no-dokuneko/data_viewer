from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_ready(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"server exited early: {output}")
        try:
            with urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"server did not become ready: {url}")


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def reset_dataset(context) -> None:
    if context.dataset.exists():
        shutil.rmtree(context.dataset)
    (context.dataset / "group-a").mkdir(parents=True)
    (context.dataset / "group-b").mkdir(parents=True)
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFElEQVR4nGP8z8DAwMDAxMDAwMAAAAwAAf4C/QcAAAAASUVORK5CYII="
    )
    (context.dataset / "group-a/01-image.png").write_bytes(png)
    (context.dataset / "group-a/01-image.caption_txt").write_text(
        "original caption", encoding="utf-8"
    )
    (context.dataset / "group-a/01-image.meta_json").write_text(
        json.dumps({"author": "Ada", "score": 0.95}), encoding="utf-8"
    )
    (context.dataset / "group-a/01-image.private_txt").write_text(
        "hidden reference", encoding="utf-8"
    )
    (context.dataset / "group-a/02-video.mp4").write_bytes(
        b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    )
    (context.dataset / "group-a/02-video.caption_txt").write_text(
        "video caption", encoding="utf-8"
    )
    (context.dataset / "group-b/03-audio.mp3").write_bytes(
        b"ID3\x04\x00\x00\x00\x00\x00\x00"
    )
    (context.dataset / "group-b/03-audio.caption_txt").write_text(
        "audio caption", encoding="utf-8"
    )
    (context.dataset / "group-b/04-note.txt").write_text(
        "acceptance note", encoding="utf-8"
    )
    (context.dataset / "group-b/04-note.caption_txt").write_text(
        "text caption", encoding="utf-8"
    )


def before_all(context) -> None:
    context.temporary = tempfile.TemporaryDirectory(prefix="data-viewer-uat-")
    context.workspace = Path(context.temporary.name)
    context.dataset = context.workspace / "dataset"
    context.report_dir = Path(os.environ["DATA_VIEWER_UAT_REPORT_DIR"])
    context.report_dir.mkdir(parents=True, exist_ok=True)
    context.python = os.environ.get("DATA_VIEWER_UAT_PYTHON", os.sys.executable)
    context.server_process = None
    context.browser = None
    context.browser_sequence = 0
    context.recorder_process = None
    reset_dataset(context)


def before_scenario(context, scenario) -> None:
    stop_process(context.server_process)
    context.server_process = None
    context.browser_sequence += 1
    slug = re.sub(r"[^\w]+", "-", scenario.name.lower()).strip("-_")
    slug = slug or f"scenario-{scenario.line}"
    context.browser_profile = (
        context.workspace / f"chrome-profile-{context.browser_sequence}-{slug}"
    )
    reset_dataset(context)
    config = context.workspace / "config.yaml"
    if config.exists():
        config.unlink()


def after_scenario(context, scenario) -> None:
    if context.browser is not None:
        slug = re.sub(r"[^\w]+", "-", scenario.name.lower()).strip("-_")
        slug = slug or f"scenario-{scenario.line}"
        context.browser.save_screenshot(str(context.report_dir / f"{slug}.png"))
        context.browser.quit()
        context.browser = None
    if context.recorder_process is not None and context.recorder_process.poll() is None:
        context.recorder_process.terminate()
        context.recorder_process.wait(timeout=5)
    context.recorder_process = None
    stop_process(context.server_process)
    context.server_process = None


def after_all(context) -> None:
    stop_process(context.server_process)
    context.temporary.cleanup()
