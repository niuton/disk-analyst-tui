from __future__ import annotations

import argparse
import sys
from pathlib import Path

import humanize

from disk_analyst_tool.core import (
    scan_directory,
    find_large_files,
    get_disk_usage,
    detect_cleanable,
    categorize_targets,
    clean,
    list_homebrew,
    list_npm_global,
    list_pip,
)


def cmd_tui() -> None:
    """Launch the TUI."""
    from disk_analyst_tool.tui.app import DiskAnalystApp

    app = DiskAnalystApp()
    app.run()


def cmd_scan(path: str) -> None:
    """Quick scan a directory."""
    usage = get_disk_usage()
    print(f"Disk: {humanize.naturalsize(usage.used)} / {humanize.naturalsize(usage.total)} ({usage.percent:.1f}%)")
    print()

    tree = scan_directory(Path(path), max_depth=2)
    _print_tree(tree, indent=0)


def _print_tree(tree, indent: int) -> None:
    prefix = "  " * indent
    size = humanize.naturalsize(tree.size)
    print(f"{prefix}{tree.name}  [{size}]")
    sorted_children = sorted(tree.children, key=lambda c: c.size, reverse=True)
    for child in sorted_children[:15]:
        _print_tree(child, indent + 1)


def cmd_cleanup() -> None:
    """Run cleanup wizard."""
    home = Path.home()
    print(f"Scanning {home}...")
    targets = detect_cleanable(home)
    categorized = categorize_targets(targets)

    safe = categorized["safe"]
    confirm = categorized["confirm"]

    if safe:
        total = sum(t.size for t in safe)
        print(f"\nAuto-cleaning {len(safe)} safe items ({humanize.naturalsize(total)})...")
        result = clean(safe, dry_run=False)
        print(f"  Freed {humanize.naturalsize(result.bytes_freed)}")

    if confirm:
        print(f"\n{len(confirm)} items need review:")
        for t in confirm:
            print(f"  [{t.category}] {t.path} ({humanize.naturalsize(t.size)})")
        answer = input("\nDelete these? [y/N] ").strip().lower()
        if answer == "y":
            result = clean(confirm, dry_run=False)
            print(f"  Freed {humanize.naturalsize(result.bytes_freed)}")
        else:
            print("  Skipped.")

    if not safe and not confirm:
        print("Nothing to clean!")


def cmd_packages() -> None:
    """List all packages."""
    for label, fn in [("Homebrew", list_homebrew), ("npm global", list_npm_global), ("pip", list_pip)]:
        pkgs = fn()
        print(f"\n{label} ({len(pkgs)}):")
        for p in sorted(pkgs, key=lambda x: x.name):
            print(f"  {p.name} {p.version}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Disk Analyst — macOS system manager")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan a directory")
    scan_p.add_argument("path", nargs="?", default=".", help="Path to scan")

    sub.add_parser("cleanup", help="Run cleanup wizard")
    sub.add_parser("packages", help="List installed packages")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args.path)
    elif args.command == "cleanup":
        cmd_cleanup()
    elif args.command == "packages":
        cmd_packages()
    else:
        cmd_tui()


if __name__ == "__main__":
    main()
