"""Command line entry point."""
from __future__ import annotations

import argparse
import sys
from importlib import resources
from pathlib import Path

from . import __version__, collect, digest, oauth
from .config import ConfigError, load

TEMPLATES = ("config.env", "channels.txt", "blocklist.txt")


def init(workdir: Path) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    for name in TEMPLATES:
        target = workdir / name
        if target.exists():
            print(f"exists, left as is: {target}")
            continue
        target.write_text(resources.files("skimtube.templates").joinpath(name)
                          .read_text(encoding="utf-8"), encoding="utf-8")
        print(f"created {target}")
    print("\nNext: set SKIMTUBE_LLM_MODEL in config.env, export SKIMTUBE_LLM_API_KEY, "
          "then run: skimtube run")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="skimtube",
        description="Turn YouTube channels into a searchable Markdown knowledge base.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-C", "--dir", type=Path, default=Path.cwd(),
                        help="working directory holding config.env, channels.txt and "
                             "state.json (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create config.env, channels.txt and blocklist.txt")
    sub.add_parser("run", help="summarize new videos into notes (idempotent; schedule it)")
    p_digest = sub.add_parser("digest", help="merge recent notes by theme, with contradictions")
    p_digest.add_argument("--window-hours", type=float, default=30,
                          help="notes collected in this window (default: 30)")
    p_digest.add_argument("--max-notes", type=int, default=150,
                          help="cap on notes sent to the LLM (default: 150)")
    sub.add_parser("auth", help="optional: authorize reading your YouTube subscriptions")
    args = parser.parse_args(argv)

    if args.command == "init":
        return init(args.dir)
    if args.command == "auth":
        return oauth.authorize()
    try:
        cfg = load(args.dir)
        if args.command == "run":
            return collect.run(cfg)
        return digest.run(cfg, args.window_hours, args.max_notes)
    except (ConfigError, collect.StateError, FileNotFoundError) as e:
        print(f"skimtube: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
