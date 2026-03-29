from unittest.mock import patch

from disk_analyst_tool.core.packages import (
    list_homebrew,
    list_npm_global,
    list_pip,
    find_orphans,
)


BREW_LIST_OUTPUT = """\
wget\t1.21.4
git\t2.43.0
jq\t1.7.1
"""


@patch("disk_analyst_tool.core.packages._run_cmd")
def test_list_homebrew(mock_run):
    mock_run.side_effect = [
        BREW_LIST_OUTPUT.strip(),  # brew list --versions
        "/opt/homebrew/Cellar",    # brew --cellar
        "/opt/homebrew",           # brew --prefix
    ]
    packages = list_homebrew()
    assert len(packages) >= 3
    assert all(p.manager == "homebrew" for p in packages)
    names = [p.name for p in packages]
    assert "wget" in names


NPM_LIST_OUTPUT = """\
/usr/local/lib
├── npm@10.2.0
├── typescript@5.3.3
└── prettier@3.1.0
"""


@patch("disk_analyst_tool.core.packages._run_cmd")
def test_list_npm_global(mock_run):
    mock_run.return_value = NPM_LIST_OUTPUT.strip()
    packages = list_npm_global()
    assert len(packages) == 3
    assert all(p.manager == "npm" for p in packages)
    names = [p.name for p in packages]
    assert "typescript" in names


PIP_LIST_OUTPUT = """\
[
  {"name": "requests", "version": "2.31.0"},
  {"name": "numpy", "version": "1.26.0"},
  {"name": "pip", "version": "24.0"}
]
"""


@patch("disk_analyst_tool.core.packages._run_cmd")
def test_list_pip(mock_run):
    mock_run.return_value = PIP_LIST_OUTPUT.strip()
    packages = list_pip()
    assert len(packages) == 3
    assert all(p.manager == "pip" for p in packages)
    names = [p.name for p in packages]
    assert "requests" in names


@patch("disk_analyst_tool.core.packages._run_cmd")
def test_find_orphans_homebrew(mock_run):
    mock_run.return_value = "jq\nwget"
    orphans = find_orphans("homebrew")
    names = [p.name for p in orphans]
    assert "jq" in names
