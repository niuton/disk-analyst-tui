from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class DockerImage:
    repository: str
    tag: str
    image_id: str
    size: int  # bytes
    created: str


@dataclass
class DockerContainer:
    container_id: str
    name: str
    image: str
    status: str
    size: int  # bytes


@dataclass
class DockerVolume:
    name: str
    driver: str
    size: int  # bytes


@dataclass
class DockerCleanResult:
    space_freed: int
    items_removed: int
    errors: list[str]


def _run_cmd(cmd: list[str], timeout: int = 30) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def is_docker_available() -> bool:
    """Check if Docker is installed and running."""
    output = _run_cmd(["docker", "info"])
    return bool(output) and "Server" in output


def list_images() -> list[DockerImage]:
    """List all Docker images with sizes."""
    output = _run_cmd(["docker", "images", "--format", "{{json .}}"])
    if not output:
        return []

    images = []
    for line in output.splitlines():
        try:
            data = json.loads(line)
            size_str = data.get("Size", "0B")
            size = _parse_docker_size(size_str)
            images.append(DockerImage(
                repository=data.get("Repository", "<none>"),
                tag=data.get("Tag", "<none>"),
                image_id=data.get("ID", ""),
                size=size,
                created=data.get("CreatedSince", ""),
            ))
        except json.JSONDecodeError:
            continue
    return sorted(images, key=lambda i: i.size, reverse=True)


def list_containers(all: bool = True) -> list[DockerContainer]:
    """List Docker containers."""
    cmd = ["docker", "ps", "--format", "{{json .}}"]
    if all:
        cmd.insert(2, "-a")
    cmd.extend(["--size"])

    output = _run_cmd(cmd, timeout=60)
    if not output:
        return []

    containers = []
    for line in output.splitlines():
        try:
            data = json.loads(line)
            size_str = data.get("Size", "0B")
            # Docker size format: "0B (virtual 123MB)"
            size = _parse_docker_size(size_str.split("(")[0].strip())
            containers.append(DockerContainer(
                container_id=data.get("ID", ""),
                name=data.get("Names", ""),
                image=data.get("Image", ""),
                status=data.get("Status", ""),
                size=size,
            ))
        except json.JSONDecodeError:
            continue
    return containers


def list_volumes() -> list[DockerVolume]:
    """List Docker volumes with sizes."""
    output = _run_cmd(["docker", "system", "df", "-v", "--format", "{{json .}}"])
    # Fallback: just list volumes
    vol_output = _run_cmd(["docker", "volume", "ls", "--format", "{{json .}}"])
    if not vol_output:
        return []

    volumes = []
    for line in vol_output.splitlines():
        try:
            data = json.loads(line)
            name = data.get("Name", "")
            driver = data.get("Driver", "")
            # Get individual volume size
            inspect = _run_cmd(["docker", "system", "df", "-v"])
            volumes.append(DockerVolume(
                name=name,
                driver=driver,
                size=0,  # Size not easily available per-volume
            ))
        except json.JSONDecodeError:
            continue
    return volumes


def get_docker_disk_usage() -> dict[str, int]:
    """Get Docker disk usage summary."""
    output = _run_cmd(["docker", "system", "df", "--format", "{{json .}}"])
    if not output:
        return {}

    result = {}
    for line in output.splitlines():
        try:
            data = json.loads(line)
            type_name = data.get("Type", "")
            size = _parse_docker_size(data.get("Size", "0B"))
            reclaimable = _parse_docker_size(data.get("Reclaimable", "0B").split("(")[0].strip())
            result[type_name] = {"size": size, "reclaimable": reclaimable}
        except (json.JSONDecodeError, ValueError):
            continue
    return result


def remove_image(image_id: str, force: bool = False) -> tuple[bool, str]:
    """Remove a Docker image."""
    cmd = ["docker", "rmi", image_id]
    if force:
        cmd.insert(2, "-f")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Removed image {image_id}"
        return False, result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)


def remove_container(container_id: str, force: bool = False) -> tuple[bool, str]:
    """Remove a Docker container."""
    cmd = ["docker", "rm", container_id]
    if force:
        cmd.insert(2, "-f")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Removed container {container_id}"
        return False, result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)


def prune_all(include_volumes: bool = False) -> DockerCleanResult:
    """Run docker system prune."""
    cmd = ["docker", "system", "prune", "-f"]
    if include_volumes:
        cmd.append("--volumes")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout

        # Parse "Total reclaimed space: X.XXGB"
        space_freed = 0
        for line in output.splitlines():
            if "reclaimed space" in line.lower():
                parts = line.split(":")
                if len(parts) >= 2:
                    space_freed = _parse_docker_size(parts[-1].strip())

        return DockerCleanResult(space_freed=space_freed, items_removed=0, errors=[])
    except (subprocess.TimeoutExpired, OSError) as e:
        return DockerCleanResult(space_freed=0, items_removed=0, errors=[str(e)])


def _parse_docker_size(size_str: str) -> int:
    """Parse Docker size strings like '1.5GB', '500MB', '10kB'."""
    size_str = size_str.strip()
    if not size_str:
        return 0

    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
        "TB": 1024 ** 4,
        "kB": 1000,
    }

    for suffix, mult in sorted(multipliers.items(), key=lambda x: len(x[0]), reverse=True):
        if size_str.upper().endswith(suffix.upper()):
            try:
                num = float(size_str[:len(size_str) - len(suffix)])
                return int(num * mult)
            except ValueError:
                return 0
    return 0
