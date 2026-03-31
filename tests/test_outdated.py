from unittest.mock import patch
from disk_analyst_tool.core.packages import (
    list_outdated_homebrew,
    list_outdated_npm,
    list_outdated_pip,
)


BREW_OUTDATED = """\
git (2.43.0) < 2.44.0
wget (1.21.4) < 1.22.0
"""


@patch("disk_analyst_tool.core.packages._run_cmd")
def test_list_outdated_homebrew(mock_run):
    mock_run.return_value = BREW_OUTDATED.strip()
    outdated = list_outdated_homebrew()
    assert len(outdated) == 2
    assert outdated[0].name == "git"
    assert outdated[0].latest == "2.44.0"


NPM_OUTDATED = '{"typescript": {"current": "5.3.3", "wanted": "5.4.0", "latest": "5.4.0"}}'


@patch("disk_analyst_tool.core.packages._run_cmd")
def test_list_outdated_npm(mock_run):
    mock_run.return_value = NPM_OUTDATED
    outdated = list_outdated_npm()
    assert len(outdated) == 1
    assert outdated[0].name == "typescript"
    assert outdated[0].current == "5.3.3"
    assert outdated[0].latest == "5.4.0"


PIP_OUTDATED = '[{"name": "requests", "version": "2.31.0", "latest_version": "2.32.0"}]'


@patch("disk_analyst_tool.core.packages._run_cmd")
def test_list_outdated_pip(mock_run):
    mock_run.return_value = PIP_OUTDATED
    outdated = list_outdated_pip()
    assert len(outdated) == 1
    assert outdated[0].name == "requests"
    assert outdated[0].latest == "2.32.0"
