from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from behave import given, then, when
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from environment import free_port, stop_process, wait_ready


KEYS = {
    "ArrowRight": Keys.ARROW_RIGHT,
    "ArrowLeft": Keys.ARROW_LEFT,
    "ArrowDown": Keys.ARROW_DOWN,
    "ArrowUp": Keys.ARROW_UP,
}


def start_server(
    context,
    *,
    password: bool = False,
    dir_mode: bool = False,
    debug_mode: bool = False,
    template: bool = False,
) -> None:
    stop_process(context.server_process)
    config = context.workspace / "config.yaml"
    if password:
        config.write_text(
            "password: uat-secret\nsecret_key: uat-session-key\n", encoding="utf-8"
        )
    elif config.exists():
        config.unlink()

    command = [
        context.python,
        str(Path(__file__).resolve().parents[2] / "serve.py"),
        str(context.dataset),
        str(free_port()),
    ]
    if not password:
        command.append("--no-login")
    if dir_mode:
        command.append("--dir-mode")
    if debug_mode:
        command.append("--debug-mode")
    if template:
        template_path = context.workspace / "template.json"
        template_path.write_text(
            json.dumps(
                {
                    "ordering": ["caption_txt", "meta_json"],
                    "annotations": {
                        "caption_txt": {"readonly": False},
                        "meta_json": {
                            "readonly": True,
                            "functions": [
                                {"name": "Author", "filter": "data['author']"}
                            ],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        command.extend(["--template", str(template_path)])

    environment = os.environ.copy()
    inherited_pythonpath = environment.get("PYTHONPATH", "")
    environment.update(
        {
            "DATA_VIEWER_UAT_CONFIG_DIR": str(context.workspace),
            "PYTHONPATH": os.pathsep.join(
                part
                for part in (
                    str(Path(__file__).resolve().parents[3]),
                    inherited_pythonpath,
                )
                if part
            ),
        }
    )
    context.server_process = subprocess.Popen(
        command,
        cwd=context.workspace,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    context.base_url = f"http://127.0.0.1:{command[3]}"
    wait_ready(f"{context.base_url}/login", context.server_process)


def ensure_browser(context) -> None:
    if context.browser is not None:
        return
    options = webdriver.ChromeOptions()
    options.binary_location = os.environ["DATA_VIEWER_UAT_BROWSER"]
    for argument in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-ipv6",
        "--remote-debugging-pipe",
        "--window-size=1440,1000",
    ):
        options.add_argument(argument)
    options.add_argument(f"--user-data-dir={context.browser_profile}")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(context.report_dir.resolve()),
            "download.prompt_for_download": False,
        },
    )
    context.browser = webdriver.Chrome(
        service=Service(os.environ["DATA_VIEWER_UAT_CHROMEDRIVER"]), options=options
    )


def wait_for(context, condition):
    return WebDriverWait(context.browser, 10).until(condition)


def make_request(
    context,
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
) -> None:
    headers = {"Content-Type": content_type} if content_type else {}
    req = Request(
        f"{context.base_url}{path}", data=body, headers=headers, method=method
    )
    try:
        with urlopen(req, timeout=10) as response:
            context.http_status = response.status
            context.http_url = response.url
            context.http_headers = dict(response.headers)
    except HTTPError as error:
        context.http_status = error.code
        context.http_url = error.url
        context.http_headers = dict(error.headers)


@given("a fresh acceptance dataset")
def fresh_dataset(context):
    assert context.dataset.is_dir()


@given("Dataset Annotator is running with password protection")
def password_server(context):
    start_server(context, password=True)


@given("Dataset Annotator is running with login disabled")
def open_server(context):
    start_server(context)


@given("Dataset Annotator is running with a demonstration dataset")
def demo_server(context):
    start_server(context)


@given("Dataset Annotator is running in directory mode")
def directory_server(context):
    start_server(context, dir_mode=True)


@given("Dataset Annotator is running in debug mode")
def debug_server(context):
    start_server(context, debug_mode=True)


@given("Dataset Annotator is running with the acceptance template")
def template_server(context):
    start_server(context, template=True)


@when('I open the web application at path "{path}"')
def open_path(context, path):
    ensure_browser(context)
    context.browser.get(f"{context.base_url}{path}")


@then("the login form is shown")
def login_form(context):
    wait_for(context, lambda d: len(d.find_elements(By.NAME, "password")) == 1)


@when('I submit password "{password}"')
def submit_password(context, password):
    field = context.browser.find_element(By.NAME, "password")
    field.clear()
    field.send_keys(password)
    field.send_keys(Keys.ENTER)


@then('the login error says "{message}"')
def login_error(context, message):
    wait_for(context, lambda d: message in d.find_element(By.TAG_NAME, "body").text)


@then("the annotator workspace is shown")
def workspace_shown(context):
    wait_for(context, lambda d: len(d.find_elements(By.ID, "page-nav")) == 1)


@then("the current media file loads after authentication")
def authenticated_media(context):
    wait_for(
        context,
        lambda d: d.find_element(By.CSS_SELECTOR, "#media-area img").get_attribute(
            "complete"
        )
        == "true",
    )


@when('I request API path "{path}" without a session')
def request_api(context, path):
    make_request(context, path)


@when('I request media path "{path}" without a session')
def request_media(context, path):
    make_request(context, path)


@then("the HTTP response status is {status:d}")
def status_is(context, status):
    assert context.http_status == status, context.http_status


@then('the HTTP response redirects to "{path}"')
def redirected_to(context, path):
    assert context.http_url.endswith(path), context.http_url


@then('item {item:d} shows an "{kind}" preview for "{filename}"')
@then('item {item:d} shows a "{kind}" preview for "{filename}"')
def media_preview(context, item, kind, filename):
    selector = {"image": "img", "video": "video", "audio": "audio", "text": "pre"}[
        kind
    ]
    wait_for(
        context,
        lambda d: d.find_element(By.ID, "page-input").get_attribute("value")
        == str(item)
        and d.find_element(By.ID, "media-info").text == filename
        and len(d.find_elements(By.CSS_SELECTOR, f"#media-area {selector}")) == 1,
    )


@then("the image resolution is visible")
def image_resolution(context):
    wait_for(context, lambda d: "2 x 2" in d.find_element(By.ID, "resolution-info").text)


@then('the text preview contains "{text}"')
def text_preview(context, text):
    wait_for(
        context, lambda d: text in d.find_element(By.CSS_SELECTOR, "#media-area pre").text
    )


@when('I press the "{key_name}" key')
def press_key(context, key_name):
    ActionChains(context.browser).send_keys(KEYS[key_name]).perform()
    time.sleep(0.2)


@when('I replace the caption with "{text}"')
def replace_caption(context, text):
    field = wait_for(
        context,
        lambda d: d.find_element(
            By.CSS_SELECTOR, '#anno-area textarea[data-filename$="caption_txt"]'
        ),
    )
    field.clear()
    field.send_keys(text)


@when('I enter quick label "{text}"')
def enter_quick(context, text):
    field = context.browser.find_element(By.ID, "quick-label")
    field.clear()
    field.send_keys(text)


@then('annotation file "{filename}" contains "{text}"')
def file_contains(context, filename, text):
    target = context.dataset / filename
    wait_for(
        context,
        lambda _d: target.exists() and text in target.read_text(encoding="utf-8"),
    )


@then('the caption editor contains "{text}"')
def caption_contains(context, text):
    wait_for(
        context,
        lambda d: d.find_element(
            By.CSS_SELECTOR, '#anno-area textarea[data-filename$="caption_txt"]'
        ).get_attribute("value")
        == text,
    )


@then('the quick-label editor contains "{text}"')
def quick_contains(context, text):
    wait_for(
        context,
        lambda d: d.find_element(By.ID, "quick-label").get_attribute("value") == text,
    )


@when("I reload the page")
def reload_page(context):
    context.browser.refresh()


@when("I jump to item {item:d}")
def jump_item(context, item):
    field = context.browser.find_element(By.ID, "page-input")
    field.clear()
    field.send_keys(str(item))
    field.send_keys(Keys.ENTER)


@when("I submit an empty page number")
def empty_page(context):
    field = context.browser.find_element(By.ID, "page-input")
    field.clear()
    field.send_keys(Keys.ENTER)


@then('item "{filename}" remains displayed with an empty page number')
def item_remains_with_empty_page(context, filename):
    wait_for(
        context,
        lambda d: d.find_element(By.ID, "media-info").text == filename
        and d.find_element(By.ID, "page-input").get_attribute("value") == "",
    )


@then("the page number is {current:d} of {total:d}")
def page_number(context, current, total):
    wait_for(
        context,
        lambda d: d.find_element(By.ID, "page-input").get_attribute("value")
        == str(current)
        and d.find_element(By.ID, "page-total").text == str(total),
    )


@then('the "{label}" badge is visible')
def badge_visible(context, label):
    wait_for(context, lambda d: label in d.find_element(By.TAG_NAME, "body").text)


@then('the quick-label filename is "{filename}"')
def quick_filename(context, filename):
    wait_for(context, lambda d: d.find_element(By.ID, "quick-name").text == filename)


@then("the caption annotation remains editable")
def caption_editable(context):
    field = wait_for(
        context,
        lambda d: d.find_element(
            By.CSS_SELECTOR, '#anno-area textarea[data-filename$="caption_txt"]'
        ),
    )
    assert field.is_enabled()


@then('the metadata summary shows "{name}" with value "{value}"')
def metadata_summary(context, name, value):
    rows = context.browser.find_elements(By.CSS_SELECTOR, ".anno-func-table tr")
    cells = [row.find_elements(By.TAG_NAME, "td") for row in rows]
    assert any(len(cell) == 2 and cell[0].text == name and cell[1].text == value for cell in cells)


@then("the private annotation is hidden")
def private_hidden(context):
    assert "private_txt" not in context.browser.find_element(By.ID, "anno-area").text


@then('the hidden badge says "{label}"')
def hidden_badge(context, label):
    wait_for(context, lambda d: d.find_element(By.ID, "hidden-label").text == label)


@when('I POST an annotation for "{filename}" with text "{text}"')
def post_annotation(context, filename, text):
    body = json.dumps(
        {"annotations": [{"filename": filename, "content": text}]}
    ).encode("utf-8")
    make_request(
        context,
        "/api/item/0",
        method="POST",
        body=body,
        content_type="application/json",
    )


@then("no file was created outside the dataset directory")
def no_outside_file(context):
    assert not (context.dataset.parent / "outside.txt").exists()


@when('I POST malformed JSON to "{path}"')
def malformed_json(context, path):
    make_request(
        context,
        path,
        method="POST",
        body=b"{broken",
        content_type="application/json",
    )


@then("the current image, caption editor, and quick-label editor are visible")
def demo_controls(context):
    media_preview(context, 1, "image", "group-a/01-image.png")
    assert context.browser.find_element(
        By.CSS_SELECTOR, '#anno-area textarea[data-filename$="caption_txt"]'
    ).is_displayed()
    assert context.browser.find_element(By.ID, "quick-label").is_displayed()
