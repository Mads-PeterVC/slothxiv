from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from slothxiv.config import ArxivSettings
from slothxiv.models import RetrievalWindow
from slothxiv.sources import SourceError
from slothxiv.sources.arxiv import ArxivSource, build_query, parse_feed


def window():
    return RetrievalWindow(start=datetime(2026, 11, 14, tzinfo=UTC),
                           end=datetime(2026, 11, 16, tzinfo=UTC))


def test_query_combines_groups_and_quotes_phrases():
    assert build_query(ArxivSettings(categories=("cs.LG", "stat.ML"), keywords=("graph learning", "biology"))) == (
        '(cat:cs.LG OR cat:stat.ML) AND ((ti:"graph learning" OR abs:"graph learning") OR '
        '(ti:"biology" OR abs:"biology"))'
    )
    assert build_query(ArxivSettings(categories=("cs.LG",))) == "(cat:cs.LG)"
    assert build_query(ArxivSettings(keywords=("graph",))) == '((ti:"graph" OR abs:"graph"))'


def test_normalizes_and_preserves_metadata(arxiv_page):
    total, start, papers = parse_feed(arxiv_page())
    assert (total, start) == (1, 0)
    paper = papers[0]
    assert paper.paper_id == "arxiv:2611.00001"
    assert paper.revision == "1"
    assert paper.title == "Graph learning for research"
    assert paper.authors == ("Ada Example", "Bo Sample")
    assert paper.categories == ("cs.LG", "stat.ML")
    assert paper.source_keywords == ()
    assert paper.metadata["doi"] == "10.0000/example"
    assert "Example University" in paper.metadata["atom_xml"]
    assert paper.published_at.year == 2025
    assert paper.updated_at.tzinfo == UTC


def test_legacy_identifiers(arxiv_page):
    paper = parse_feed(arxiv_page([("cond-mat/0207270v2", "2026-11-15T00:00:00Z")]))[2][0]
    assert paper.source_id == "cond-mat/0207270"
    assert paper.revision == "2"


@pytest.mark.parametrize("data", [b"broken", b"<html/>", b'''<!DOCTYPE feed [
<!ENTITY x "injected">]><feed xmlns="http://www.w3.org/2005/Atom">&x;</feed>'''])
def test_rejects_malformed_and_entity_xml(data):
    with pytest.raises(SourceError):
        parse_feed(data)


@pytest.mark.parametrize("old,new", [
    (b"2611.00001v1", b"2611.00001"),
    (b"2026-11-15T12:00:00Z", b"2026-11-15T12:00:00"),
    (b"Ada Example", b""),
    (b">1</", b">not-a-number</"),
])
def test_rejects_invalid_metadata(arxiv_page, old, new):
    with pytest.raises(SourceError):
        parse_feed(arxiv_page().replace(old, new))


def test_api_error_is_not_empty_success(arxiv_page):
    data = arxiv_page().replace(b"http://arxiv.org/abs/2611.00001v1", b"http://arxiv.org/api/errors#bad_query")
    with pytest.raises(SourceError, match="API error"):
        parse_feed(data)


def test_pagination_exact_window_and_old_revision(arxiv_page):
    pages = [
        arxiv_page([("2611.00003v1", "2026-11-16T00:00:00Z"),
                    ("2611.00002v1", "2026-11-15T00:00:00Z")], total=4),
        arxiv_page([("cond-mat/0207270v2", "2026-11-14T00:00:00Z"),
                    ("2611.00001v1", "2026-11-13T23:59:59Z")], total=4, start=2),
    ]
    requests, sleeps = [], []

    def transport(url):
        requests.append(parse_qs(urlsplit(url).query))
        return pages.pop(0)

    source = ArxivSource(ArxivSettings(categories=("cs.LG",)), transport=transport, page_size=2, sleep=sleeps.append)
    papers = list(source.fetch(window()))
    assert [paper.source_id for paper in papers] == ["2611.00002", "cond-mat/0207270"]
    assert [request["start"] for request in requests] == [["0"], ["2"]]
    assert requests[0]["sortBy"] == ["lastUpdatedDate"]
    assert "submittedDate" not in requests[0]["search_query"][0]
    assert sleeps == [3]


def test_empty_feed(arxiv_page):
    source = ArxivSource(ArxivSettings(keywords=("graphs",)), transport=lambda _: arxiv_page([]))
    assert list(source.fetch(window())) == []


def test_result_cap_fails_instead_of_succeeding_with_truncation(arxiv_page, monkeypatch):
    import slothxiv.sources.arxiv as arxiv

    monkeypatch.setattr(arxiv, "RESULT_LIMIT", 1)
    source = ArxivSource(ArxivSettings(categories=("cs.LG",)), page_size=1,
                         transport=lambda _: arxiv_page(total=2))
    with pytest.raises(SourceError, match="narrow"):
        list(source.fetch(window()))


def test_stops_at_lower_boundary_without_requesting_more(arxiv_page):
    requests = []

    def transport(url):
        requests.append(url)
        return arxiv_page([("2611.00001v1", "2026-11-13T00:00:00Z")], total=100)

    source = ArxivSource(ArxivSettings(categories=("cs.LG",)), transport=transport)
    assert list(source.fetch(window())) == []
    assert len(requests) == 1


def test_changing_total_fails(arxiv_page):
    pages = [arxiv_page(total=2), arxiv_page([
        ("2611.00002v1", "2026-11-14T00:00:00Z"),
    ], total=3, start=1)]
    source = ArxivSource(ArxivSettings(categories=("cs.LG",)), page_size=1,
                         transport=lambda _: pages.pop(0), sleep=lambda _: None)
    with pytest.raises(SourceError, match="count changed"):
        list(source.fetch(window()))


@pytest.mark.parametrize("case", ["empty", "offset", "ordering", "duplicate"])
def test_incomplete_or_inconsistent_pages_fail(arxiv_page, case):
    pages = {
        "empty": [arxiv_page([], total=2)],
        "offset": [arxiv_page(start=1)],
        "ordering": [arxiv_page([("2611.00001v1", "2026-11-14T00:00:00Z"),
                                    ("2611.00002v1", "2026-11-15T00:00:00Z")])],
        "duplicate": [arxiv_page(total=2), arxiv_page(start=1, total=2)],
    }[case]
    source = ArxivSource(ArxivSettings(categories=("cs.LG",)), transport=lambda _: pages.pop(0), sleep=lambda _: None)
    with pytest.raises(SourceError):
        list(source.fetch(window()))


def test_transport_failure():
    def broken(_):
        raise TimeoutError("timeout")

    with pytest.raises(SourceError, match="request failed"):
        list(ArxivSource(ArxivSettings(categories=("cs.LG",)), transport=broken).fetch(window()))
