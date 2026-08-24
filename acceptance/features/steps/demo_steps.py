from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import time

from behave import given, step, then, when


def hook_parts(value: str, mapping: dict[str, str]) -> list[str]:
    return [part.format_map(mapping) for part in shlex.split(value)]


@given("I begin a recorded demo")
def begin_recording(context):
    feature_name = Path(context.feature.filename).stem
    context.demo_output = context.report_dir / f"{feature_name}.mp4"
    command = os.environ.get("DEMO_RECORD_START_COMMAND", "").strip()
    if command:
        context.recorder_process = subprocess.Popen(
            hook_parts(command, {"output": str(context.demo_output)}), cwd=Path.cwd()
        )


@step('I narrate in "{locale}" for at least {seconds:d} seconds:')
def narrate(context, locale, seconds):
    text = (context.text or "").strip()
    started = time.monotonic()
    command = os.environ.get("DEMO_TTS_COMMAND", "").strip()
    if command:
        subprocess.run(
            hook_parts(
                command,
                {"locale": locale, "text": text, "seconds": str(seconds)},
            ),
            check=True,
        )
    else:
        print(f"[{locale}] {text}")
    remaining = seconds - (time.monotonic() - started)
    if remaining > 0:
        time.sleep(remaining)


@when("I pause for {seconds:d} seconds")
def pause(_context, seconds):
    time.sleep(seconds)


@then("I finish the recorded demo")
def finish_recording(context):
    context.browser.save_screenshot(str(context.report_dir / "demo-final.png"))
    command = os.environ.get("DEMO_RECORD_STOP_COMMAND", "").strip()
    if command:
        subprocess.run(
            hook_parts(command, {"output": str(context.demo_output)}), check=True
        )
    if context.recorder_process is not None and context.recorder_process.poll() is None:
        context.recorder_process.terminate()
        context.recorder_process.wait(timeout=5)
    context.recorder_process = None
