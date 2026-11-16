"""Smoke checks for the installed package and its console entry point."""

from importlib.metadata import distribution

import slothxiv


def test_console_entry_point_resolves_to_package_main() -> None:
    entry_points = [
        entry
        for entry in distribution("slothxiv").entry_points
        if entry.group == "console_scripts" and entry.name == "slothxiv"
    ]

    assert len(entry_points) == 1
    assert entry_points[0].load() is slothxiv.main
    assert callable(slothxiv.main)
