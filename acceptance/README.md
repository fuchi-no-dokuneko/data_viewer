# Executable acceptance suites

The daily suite is a granular checklist for a human or browser agent. The two
demo suites are timed English and Cantonese product introductions. Dry mode
loads every feature and verifies that every Gherkin step has an implementation
without starting Flask or a browser.

```bash
python -m pip install -r requirements.txt -r acceptance/requirements.txt
python acceptance/run.py --suite all --dry-run
python acceptance/run.py --suite uat
python acceptance/run.py --suite demo-en
python acceptance/run.py --suite demo-yue
```

A real run requires Chromium and `chromedriver`. Reports and scenario
screenshots are written to `build/reports/uat/` as `checklist.json`,
`sonar-test-execution.xml`, and PNG artifacts. A missing browser causes the
whole selected GUI suite to stop before any scenario begins.

Recording integrations are optional command templates. They are tokenized
without a shell:

- `DEMO_RECORD_START_COMMAND`, with `{output}` available
- `DEMO_RECORD_STOP_COMMAND`, with `{output}` available
- `DEMO_TTS_COMMAND`, with `{locale}`, `{text}`, and `{seconds}` available

Without a TTS command, narration is printed and the runner still waits for the
declared minimum duration so manual speech and actions remain synchronized.

## Feature coverage matrix

| Product feature | Daily scenario | Demo |
| --- | --- | --- |
| Password rejection, login, protected files/API | Password login; Protected API and media | No |
| Image, video, audio, and text previews | Every supported media type | Main flow starts with image |
| Caption and quick-label save/persistence | Caption and quick-label changes | English and Cantonese main flow |
| Arrow navigation, wrap, number jump, resume | Number navigation; Previous and next navigation | Arrow save/return explained |
| Directory labels and directory transitions | Directory mode | Explained |
| Debug indicator | Debug mode | No |
| Template edit/read-only summary/hiding | Template separates annotations | Explained |
| Invalid payload, traversal, and missing file recovery | Save validation; Missing items | No |

The Fernet encrypt/decrypt endpoints have no visible control in the current UI;
they remain backend API behavior and are outside this GUI acceptance matrix.
