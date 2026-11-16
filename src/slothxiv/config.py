"""TOML profiles and working-directory-independent path resolution."""

from pathlib import Path
import tomllib
from typing import Annotated

from platformdirs import user_config_path, user_data_path
from pydantic import Field, StringConstraints, field_validator, model_validator

from slothxiv.models import Model, NonEmpty

Category = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9.-]*$")]


class ArxivSettings(Model):
    categories: tuple[Category, ...] = ()
    keywords: tuple[NonEmpty, ...] = ()

    @field_validator("keywords")
    @classmethod
    def literal_keywords(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            if any(char in value for char in '"\\*?') or any(
                ord(char) < 32 for char in value
            ):
                raise ValueError("keywords cannot contain quotes, backslashes, wildcards, or controls")
        return values

    @model_validator(mode="after")
    def has_criteria(self) -> "ArxivSettings":
        if not self.categories and not self.keywords:
            raise ValueError("provide at least one category or keyword")
        return self


class EvaluationSettings(Model):
    instructions: NonEmpty
    model: NonEmpty = "sonnet"
    timeout_seconds: Annotated[int, Field(strict=True, gt=0, le=86400)] = 120


class Profile(Model):
    lookback_days: Annotated[int, Field(strict=True, gt=0, le=365000)]
    arxiv: ArxivSettings
    evaluation: EvaluationSettings | None = None


class StorageSettings(Model):
    database: Path | None = None


class Configuration(Model):
    profiles: Annotated[dict[NonEmpty, Profile], Field(min_length=1)]
    storage: StorageSettings = Field(default_factory=StorageSettings)


def default_config_path() -> Path:
    return user_config_path("slothxiv", appauthor=False) / "config.toml"


def default_database_path() -> Path:
    return user_data_path("slothxiv", appauthor=False) / "slothxiv.sqlite3"


def load_config(path: Path | None = None) -> Configuration:
    """Resolve a configured relative database path against the configuration file."""
    config_path = (path or default_config_path()).expanduser().resolve()
    with config_path.open("rb") as stream:
        config = Configuration.model_validate(tomllib.load(stream))
    database = config.storage.database
    if database is not None:
        database = database.expanduser()
        if not database.is_absolute():
            database = config_path.parent / database
        config = config.model_copy(update={
            "storage": StorageSettings(database=database.resolve()),
        })
    return config
