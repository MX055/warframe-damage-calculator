from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_PATTERNS = ("*.py", "*.md", "*.toml")
EXCLUDED_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"}


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def collect_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        for candidate in root.rglob(pattern):
            if candidate.is_file() and not should_skip(candidate):
                files.add(candidate)
    return sorted(files)


def rewrite_file(path: Path) -> None:
    # Read and write exact bytes to force an on-disk rewrite without content changes.
    payload = path.read_bytes()
    with path.open("wb") as handle:
        handle.write(payload)
        handle.flush()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite selected repository files in-place on disk without changing content."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Repository root to scan (defaults to current directory).",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="Glob pattern to include (can be used multiple times). Defaults: *.py, *.md, *.toml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print files that would be rewritten.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Invalid directory: {root}")
        return 1

    patterns = tuple(args.pattern) if args.pattern else DEFAULT_PATTERNS
    targets = collect_files(root, patterns)

    if not targets:
        print("No matching files found.")
        return 0

    print(f"Found {len(targets)} files under {root}:")
    for path in targets:
        print(f"- {path}")

    if args.dry_run:
        print("Dry run complete. No files were rewritten.")
        return 0

    for path in targets:
        rewrite_file(path)

    print(f"Rewrote {len(targets)} files in place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
