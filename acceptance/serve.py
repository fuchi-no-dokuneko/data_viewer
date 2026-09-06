from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("port", type=int)
    parser.add_argument("--dir-mode", action="store_true")
    parser.add_argument("--debug-mode", action="store_true")
    parser.add_argument("--template", type=Path)
    parser.add_argument("--no-login", action="store_true")
    args = parser.parse_args()

    app_path = ROOT / "app.py"
    app_argv = [str(app_path), str(args.dataset)]
    if args.dir_mode:
        app_argv.append("--dir")
    if args.debug_mode:
        app_argv.append("--debug")
    if args.template:
        app_argv.extend(["--template", str(args.template)])
    if args.no_login:
        app_argv.append("--no-login")

    sys.argv = app_argv
    os.chdir(os.environ["DATA_VIEWER_UAT_CONFIG_DIR"])
    spec = importlib.util.spec_from_file_location("data_viewer_acceptance_app", app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Dataset Annotator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.app.run(
        host="127.0.0.1", port=args.port, threaded=True, use_reloader=False
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
