from __future__ import annotations

import argparse
import shutil
from pathlib import Path

TARGET_NAMES = {"__pycache__"}


def find_cache_dirs(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_dir() and path.name in TARGET_NAMES
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete Python bytecode cache folders from a repository."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Repository root to clean (defaults to current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show directories that would be deleted without removing them.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Invalid directory: {root}")
        return 1

    cache_dirs = find_cache_dirs(root)
    if not cache_dirs:
        print("No cache directories found.")
        return 0

    print(f"Found {len(cache_dirs)} cache directories under {root}:")
    for directory in cache_dirs:
        print(f"- {directory}")

    if args.dry_run:
        print("Dry run complete. No directories were deleted.")
        return 0

    removed = 0
    for directory in cache_dirs:
        shutil.rmtree(directory, ignore_errors=False)
        removed += 1

    print(f"Deleted {removed} cache directories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
