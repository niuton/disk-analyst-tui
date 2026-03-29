from unittest.mock import patch

from disk_analyst_tool.core.docker import (
    _parse_docker_size,
    is_docker_available,
    list_images,
    DockerImage,
)


def test_parse_docker_size_gb():
    assert _parse_docker_size("1.5GB") == int(1.5 * 1024 ** 3)


def test_parse_docker_size_mb():
    assert _parse_docker_size("500MB") == int(500 * 1024 ** 2)


def test_parse_docker_size_kb():
    assert _parse_docker_size("10KB") == int(10 * 1024)


def test_parse_docker_size_bytes():
    assert _parse_docker_size("100B") == 100


def test_parse_docker_size_empty():
    assert _parse_docker_size("") == 0


DOCKER_IMAGES_OUTPUT = """\
{"ID":"abc123","Repository":"nginx","Tag":"latest","Size":"150MB","CreatedSince":"2 weeks ago"}
{"ID":"def456","Repository":"python","Tag":"3.13","Size":"1.2GB","CreatedSince":"3 days ago"}
"""


@patch("disk_analyst_tool.core.docker._run_cmd")
def test_list_images(mock_run):
    mock_run.return_value = DOCKER_IMAGES_OUTPUT.strip()
    images = list_images()
    assert len(images) == 2
    assert images[0].repository == "python"  # sorted by size desc
    assert images[0].size > images[1].size


@patch("disk_analyst_tool.core.docker._run_cmd")
def test_is_docker_available_true(mock_run):
    mock_run.return_value = "Server: Docker Engine"
    assert is_docker_available() is True


@patch("disk_analyst_tool.core.docker._run_cmd")
def test_is_docker_available_false(mock_run):
    mock_run.return_value = ""
    assert is_docker_available() is False
