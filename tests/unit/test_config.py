from pathlib import Path

import pytest
from pydantic import ValidationError

from slothxiv.config import ArxivSettings, Configuration, Profile, load_config


def test_load_relative_database_independent_of_cwd(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text('''
[storage]
database = "state/history.db"
[profiles.graphs]
lookback_days = 2
[profiles.graphs.arxiv]
categories = ["cs.LG"]
keywords = ["graph learning"]
[profiles.statistics]
lookback_days = 7
[profiles.statistics.arxiv]
categories = ["stat.ML"]
''')
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    config = load_config(path)
    assert config.storage.database == tmp_path / "state/history.db"
    assert config.profiles["statistics"].lookback_days == 7


@pytest.mark.parametrize("days", [None, 0, -1, 1.5, "2", True])
def test_requires_positive_integer_lookback(days):
    values = {"arxiv": {"categories": ["cs.LG"]}}
    if days is not None:
        values["lookback_days"] = days
    with pytest.raises(ValidationError):
        Profile.model_validate(values)


@pytest.mark.parametrize("settings", [
    {}, {"categories": ["cs.LG OR all:*"]}, {"keywords": [" "]},
    {"keywords": ['a" OR all:*']}, {"keywords": ["graph*"]},
    {"keywords": ["graph\nlearning"]}, {"unknown": True},
])
def test_rejects_invalid_or_unbounded_criteria(settings):
    with pytest.raises(ValidationError):
        ArxivSettings.model_validate(settings)


def test_unknown_config_keys_are_rejected():
    with pytest.raises(ValidationError):
        Configuration.model_validate({"profiles": {}, "typo": True})


def test_user_defaults_do_not_follow_working_directory(tmp_path, monkeypatch):
    from slothxiv.config import default_config_path, default_database_path

    config, database = default_config_path(), default_database_path()
    monkeypatch.chdir(tmp_path)
    assert default_config_path() == config
    assert default_database_path() == database
    assert config.is_absolute() and database.is_absolute()


def test_tilde_database_expands(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / "config.toml"
    path.write_text('''
[storage]
database = "~/data/papers.db"
[profiles.example]
lookback_days = 1
[profiles.example.arxiv]
keywords = ["graphs"]
''')
    assert load_config(path).storage.database == Path.home() / "data/papers.db"
