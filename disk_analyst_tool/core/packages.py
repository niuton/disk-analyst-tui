from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from disk_analyst_tool.core.models import Package


def _run_cmd(cmd: list[str], timeout: int = 30) -> str:
    """Run a shell command and return stdout. Returns empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory."""
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def list_homebrew() -> list[Package]:
    """List installed Homebrew formulae and casks with sizes."""
    output = _run_cmd(["brew", "list", "--versions"])
    if not output:
        return []

    cellar = _run_cmd(["brew", "--cellar"])
    caskroom = _run_cmd(["brew", "--prefix"])
    caskroom = str(Path(caskroom) / "Caskroom") if caskroom else ""

    packages: list[Package] = []
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            name = parts[0]
            version = parts[-1]

            # Calculate size from Cellar or Caskroom
            size = 0
            if cellar:
                pkg_path = Path(cellar) / name
                if pkg_path.exists():
                    size = _dir_size(pkg_path)
            if size == 0 and caskroom:
                pkg_path = Path(caskroom) / name
                if pkg_path.exists():
                    size = _dir_size(pkg_path)

            packages.append(
                Package(name=name, version=version, size=size, manager="homebrew")
            )
    return packages


def list_npm_global() -> list[Package]:
    """List globally installed npm packages with sizes."""
    output = _run_cmd(["npm", "list", "-g", "--depth=0"])
    if not output:
        return []

    npm_root = _run_cmd(["npm", "root", "-g"])

    packages: list[Package] = []
    for line in output.splitlines():
        match = re.search(r"[├└]──\s+(.+)@(.+)$", line)
        if match:
            name, version = match.group(1), match.group(2)

            size = 0
            if npm_root:
                pkg_path = Path(npm_root) / name
                if pkg_path.exists():
                    size = _dir_size(pkg_path)

            packages.append(
                Package(name=name, version=version, size=size, manager="npm")
            )
    return packages


def list_pip() -> list[Package]:
    """List installed pip packages with sizes."""
    output = _run_cmd(["pip", "list", "--format=json"])
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    # Get site-packages directory
    site_dir = _run_cmd(["python", "-c", "import site; print(site.getsitepackages()[0])"])

    packages: list[Package] = []
    for item in data:
        name = item["name"]
        version = item["version"]

        size = 0
        if site_dir:
            # pip packages can be in name/ or name.dist-info/
            # Check the actual package directory
            pkg_dir = Path(site_dir) / name.replace("-", "_")
            if pkg_dir.exists():
                size = _dir_size(pkg_dir)
            else:
                # Try lowercase
                pkg_dir = Path(site_dir) / name.replace("-", "_").lower()
                if pkg_dir.exists():
                    size = _dir_size(pkg_dir)

            # Also add dist-info size
            for suffix in [".dist-info", ".egg-info"]:
                normalized = name.replace("-", "_")
                info_dir = Path(site_dir) / f"{normalized}-{version}{suffix}"
                if info_dir.exists():
                    size += _dir_size(info_dir)

        packages.append(
            Package(name=name, version=version, size=size, manager="pip")
        )
    return packages


def find_orphans(manager: str) -> list[Package]:
    """Find packages that nothing else depends on."""
    if manager == "homebrew":
        output = _run_cmd(["brew", "autoremove", "--dry-run"])
        if not output:
            return []
        return [
            Package(name=line.strip(), version="", size=0, manager="homebrew", is_orphan=True)
            for line in output.splitlines()
            if line.strip() and not line.startswith("=")
        ]
    return []


@dataclass
class OutdatedPackage:
    name: str
    current: str
    latest: str
    manager: str


def list_outdated_homebrew() -> list[OutdatedPackage]:
    """List outdated Homebrew packages."""
    output = _run_cmd(["brew", "outdated", "--verbose"], timeout=60)
    if not output:
        return []

    results = []
    for line in output.splitlines():
        # Format: "package (1.0 < 2.0)" or "package (1.0) < 2.0"
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        name = parts[0]
        # Extract versions from the rest
        rest = " ".join(parts[1:])
        rest = rest.strip("()")
        if "<" in rest:
            versions = rest.split("<")
            current = versions[0].strip().strip("()")
            latest = versions[-1].strip().strip("()")
            results.append(OutdatedPackage(name=name, current=current, latest=latest, manager="homebrew"))
        elif len(parts) >= 2:
            results.append(OutdatedPackage(name=name, current=parts[1] if len(parts) > 1 else "?", latest="?", manager="homebrew"))
    return results


def list_outdated_npm() -> list[OutdatedPackage]:
    """List outdated global npm packages."""
    output = _run_cmd(["npm", "outdated", "-g", "--json"], timeout=60)
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    return [
        OutdatedPackage(
            name=name,
            current=info.get("current", "?"),
            latest=info.get("latest", "?"),
            manager="npm",
        )
        for name, info in data.items()
    ]


def list_outdated_pip() -> list[OutdatedPackage]:
    """List outdated pip packages."""
    output = _run_cmd(["pip", "list", "--outdated", "--format=json"], timeout=60)
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    return [
        OutdatedPackage(
            name=item["name"],
            current=item.get("version", "?"),
            latest=item.get("latest_version", "?"),
            manager="pip",
        )
        for item in data
    ]


def uninstall(package: Package) -> tuple[bool, str]:
    """Uninstall a package using its manager. Returns (success, message)."""
    cmds = {
        "homebrew": ["brew", "uninstall", package.name],
        "npm": ["npm", "uninstall", "-g", package.name],
        "pip": ["pip", "uninstall", "-y", package.name],
    }
    cmd = cmds.get(package.manager)
    if not cmd:
        return False, f"Unknown manager: {package.manager}"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, f"Uninstalled {package.name}"
        return False, result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)
