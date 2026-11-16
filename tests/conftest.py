"""Small Atom fixture factory shared by source and workflow tests."""

from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Keep accidental live requests out of the default suite."""
    import socket

    def blocked(*args, **kwargs):
        raise AssertionError("network access is forbidden in offline tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def arxiv_page():
    template = ET.fromstring((Path(__file__).parent / "fixtures/arxiv.xml").read_bytes())
    atom = "{http://www.w3.org/2005/Atom}"
    open_search = "{http://a9.com/-/spec/opensearch/1.1/}"

    def make(rows=None, *, total=None, start=0):
        if rows is None:
            rows = [("2611.00001v1", "2026-11-15T12:00:00Z")]
        root = deepcopy(template)
        entry = root.find(atom + "entry")
        root.remove(entry)
        root.find(open_search + "totalResults").text = str(len(rows) if total is None else total)
        root.find(open_search + "startIndex").text = str(start)
        root.find(open_search + "itemsPerPage").text = str(len(rows))
        for identifier, updated in rows:
            copy = deepcopy(entry)
            copy.find(atom + "id").text = f"http://arxiv.org/abs/{identifier}"
            copy.find(atom + "updated").text = updated
            root.append(copy)
        return ET.tostring(root)

    return make
