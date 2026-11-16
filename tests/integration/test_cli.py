from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

import pytest

from slothxiv.cli import main
from slothxiv.storage.sqlite import SQLiteStore


def write_config(path):
    path.write_text('''
[storage]
database = "state/papers.db"
[profiles.graphs]
lookback_days = 2
[profiles.graphs.arxiv]
keywords = ["graph learning"]
''')


def test_cli_real_components_with_fake_http(tmp_path, monkeypatch, capsys, arxiv_page):
    import slothxiv.sources.arxiv as arxiv

    config = tmp_path / "config.toml"
    write_config(config)
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setattr(arxiv, "urlopen", lambda request, timeout: BytesIO(arxiv_page([])))
    main(["scrape", "--config", str(config), "--profile", "graphs"])
    assert "0 paper revision(s)" in capsys.readouterr().out
    with SQLiteStore(tmp_path / "state/papers.db") as store:
        assert store.list_runs()[0].status == "completed"


def test_explicit_database_overrides_config(tmp_path, monkeypatch, arxiv_page):
    import slothxiv.sources.arxiv as arxiv

    config = tmp_path / "config.toml"
    write_config(config)
    database = tmp_path / "override.db"
    monkeypatch.setattr(arxiv, "urlopen", lambda request, timeout: BytesIO(arxiv_page([])))
    main(["scrape", "--config", str(config), "--database", str(database), "--profile", "graphs"])
    assert database.exists()
    assert not (tmp_path / "state").exists()


def test_scrape_json_output(tmp_path, monkeypatch, capsys, arxiv_page):
    import slothxiv.sources.arxiv as arxiv

    config = tmp_path / "config.toml"
    write_config(config)
    monkeypatch.setattr(arxiv, "urlopen", lambda request, timeout: BytesIO(arxiv_page([])))
    main(["scrape", "--config", str(config), "--profile", "graphs", "--format", "json"])
    output = json.loads(capsys.readouterr().out)
    assert output["retrieval"]["status"] == "completed"
    assert output["retrieval"]["observation_count"] == 0
    assert output["database"] == str(tmp_path / "state/papers.db")


def test_cli_source_failure_has_nonzero_exit_and_persisted_run(tmp_path, monkeypatch, capsys):
    import slothxiv.sources.arxiv as arxiv

    config = tmp_path / "config.toml"
    write_config(config)

    def timeout(request, timeout):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(arxiv, "urlopen", timeout)
    with pytest.raises(SystemExit) as caught:
        main(["scrape", "--config", str(config), "--profile", "graphs"])
    assert caught.value.code == 1
    assert "retrieval failed (run " in capsys.readouterr().err
    with SQLiteStore(tmp_path / "state/papers.db") as store:
        assert store.list_runs()[0].status == "failed"


@pytest.mark.parametrize("case", ["missing_config", "unknown_profile", "invalid_toml", "missing_profile"])
def test_cli_configuration_errors_do_not_create_database(tmp_path, capsys, case):
    config = tmp_path / "config.toml"
    write_config(config)
    args = ["scrape", "--config", str(config), "--profile", "graphs"]
    if case == "missing_config":
        args[2] = str(tmp_path / "missing.toml")
    elif case == "unknown_profile":
        args[-1] = "absent"
    elif case == "invalid_toml":
        config.write_text("[invalid")
    else:
        args = args[:-2]
    with pytest.raises(SystemExit) as caught:
        main(args)
    assert caught.value.code in (1, 2)
    assert capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_installed_entry_point_outside_repo_with_fixture_http(tmp_path, arxiv_page):
    """Run the installed entry point in a child interpreter; replace only HTTP."""
    config = tmp_path / "config.toml"
    write_config(config)
    fixture = tmp_path / "response.xml"
    fixture.write_bytes(arxiv_page([]))
    other = tmp_path / "elsewhere"
    other.mkdir()
    script = '''
from importlib.metadata import distribution
from io import BytesIO
from pathlib import Path
import socket
import sys
import slothxiv.sources.arxiv as arxiv
def blocked(*args, **kwargs):
    raise AssertionError("unexpected network request")
socket.socket.connect = blocked
response_bytes = Path(sys.argv[1]).read_bytes()
arxiv.urlopen = lambda request, timeout: BytesIO(response_bytes)
sys.argv = ["slothxiv", "scrape", "--config", sys.argv[2], "--profile", "graphs"]
entry = next(e for e in distribution("slothxiv").entry_points if e.name == "slothxiv")
entry.load()()
'''
    result = subprocess.run([sys.executable, "-c", script, str(fixture), str(config)],
                            cwd=other, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "Completed run" in result.stdout
    with SQLiteStore(tmp_path / "state/papers.db") as store:
        assert store.list_runs()[0].status == "completed"
    executable = Path(sys.executable).parent / "slothxiv"
    result = subprocess.run([str(executable), "scrape", "--help"], cwd=other,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "--profile" in result.stdout
