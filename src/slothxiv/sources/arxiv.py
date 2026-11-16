"""arXiv Atom parsing, queries, and update-time retrieval."""

from collections.abc import Callable, Iterator
from datetime import datetime
import re
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, ParseError, tostring

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException
from pydantic import ValidationError

from slothxiv.config import ArxivSettings
from slothxiv.models import Paper, RetrievalWindow
from slothxiv.sources import SourceError

ATOM = "{http://www.w3.org/2005/Atom}"
OPEN = "{http://a9.com/-/spec/opensearch/1.1/}"
ARXIV = "{http://arxiv.org/schemas/atom}"
ENDPOINT = "https://export.arxiv.org/api/query"
RESULT_LIMIT = 30000
IDENTIFIER = re.compile(r"^(\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?/\d{7})v([1-9]\d*)$")


def build_query(settings: ArxivSettings) -> str:
    groups = []
    if settings.categories:
        groups.append("(" + " OR ".join(f"cat:{cat}" for cat in settings.categories) + ")")
    if settings.keywords:
        groups.append("(" + " OR ".join(
            f'(ti:"{word}" OR abs:"{word}")' for word in settings.keywords
        ) + ")")
    return " AND ".join(groups)


def required(element: Element, tag: str) -> str:
    text = element.findtext(tag)
    if text is None or not text.strip():
        raise SourceError(f"arXiv response missing {tag}")
    return " ".join(text.split())


def parse_entry(entry: Element) -> Paper:
    identifier_url = required(entry, ATOM + "id")
    parsed = urlsplit(identifier_url)
    match = IDENTIFIER.fullmatch(parsed.path.removeprefix("/abs/"))
    if parsed.hostname != "arxiv.org" or not parsed.path.startswith("/abs/") or not match:
        raise SourceError("arXiv response contains an invalid versioned identifier")
    source_id, revision = match.groups()
    pdf = next((link.get("href") for link in entry.findall(ATOM + "link")
                if link.get("title") == "pdf"), None)
    metadata = {"atom_xml": tostring(entry, encoding="unicode")}
    for tag in ("doi", "comment", "journal_ref"):
        value = entry.findtext(ARXIV + tag)
        if value:
            metadata[tag] = value
    primary = entry.find(ARXIV + "primary_category")
    if primary is not None and primary.get("term"):
        metadata["primary_category"] = primary.get("term")
    try:
        return Paper(
            source="arxiv", source_id=source_id, revision=revision,
            title=required(entry, ATOM + "title"),
            abstract=required(entry, ATOM + "summary"),
            authors=tuple(required(author, ATOM + "name") for author in entry.findall(ATOM + "author")),
            published_at=required(entry, ATOM + "published"),
            updated_at=required(entry, ATOM + "updated"),
            url=f"https://arxiv.org/abs/{source_id}v{revision}", pdf_url=pdf,
            categories=tuple(required_term(category) for category in entry.findall(ATOM + "category")),
            metadata=metadata,
        )
    except ValidationError as error:
        raise SourceError("arXiv entry contains invalid paper metadata") from error


def required_term(category: Element) -> str:
    term = category.get("term", "").strip()
    if not term:
        raise SourceError("arXiv category has no term")
    return term


def parse_feed(data: bytes) -> tuple[int, int, list[Paper]]:
    """Reject errors and malformed pages rather than silently dropping entries."""
    try:
        root = fromstring(data)
        if root.tag != ATOM + "feed":
            raise SourceError("arXiv response is not an Atom feed")
        entries = root.findall(ATOM + "entry")
        if any("/api/errors" in (entry.findtext(ATOM + "id") or "") for entry in entries):
            raise SourceError("arXiv returned an API error feed")
        total = int(required(root, OPEN + "totalResults"))
        start = int(required(root, OPEN + "startIndex"))
        if total < 0 or start < 0:
            raise ValueError("negative pagination metadata")
        return total, start, [parse_entry(entry) for entry in entries]
    except (ParseError, DefusedXmlException, ValueError) as error:
        raise SourceError("arXiv returned malformed XML or pagination metadata") from error


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "slothxiv/0.1.0", "Accept": "application/atom+xml"})
    with urlopen(request, timeout=30) as response:
        return response.read()


class ArxivSource:
    name = "arxiv"

    def __init__(
        self, settings: ArxivSettings, *, transport: Callable[[str], bytes] = download,
        page_size: int = 100, sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= page_size <= 2000:
            raise ValueError("page_size must be between 1 and 2000")
        self.settings = settings
        self.transport = transport
        self.page_size = page_size
        self.sleep = sleep
        self._requested = False

    def fetch(self, window: RetrievalWindow) -> Iterator[Paper]:
        # Only submittedDate filtering is documented by arXiv. Applying it would
        # lose revisions of older papers, so scan by descending lastUpdatedDate.
        start = 0
        previous: datetime | None = None
        expected_total: int | None = None
        seen: set[tuple[str, str]] = set()
        while True:
            if self._requested:
                self.sleep(3)
            self._requested = True
            url = ENDPOINT + "?" + urlencode({
                "search_query": build_query(self.settings), "start": start,
                "max_results": self.page_size, "sortBy": "lastUpdatedDate",
                "sortOrder": "descending",
            })
            try:
                total, returned_start, papers = parse_feed(self.transport(url))
            except SourceError:
                raise
            except (OSError, ValueError) as error:
                raise SourceError("arXiv request failed") from error
            if (returned_start != start or len(papers) > self.page_size
                    or (papers and start + len(papers) > total)):
                raise SourceError("arXiv returned inconsistent pagination")
            if not papers and start < total:
                raise SourceError("arXiv returned an incomplete page")
            if expected_total is not None and total != expected_total:
                raise SourceError("arXiv result count changed during pagination; rerun retrieval")
            expected_total = total
            for paper in papers:
                if previous is not None and paper.updated_at > previous:
                    raise SourceError("arXiv results are not ordered by update time")
                previous = paper.updated_at
                if paper.updated_at < window.start:
                    return
                key = (paper.source_id, paper.revision)
                if key in seen:
                    raise SourceError("arXiv repeated a revision during pagination; rerun retrieval")
                seen.add(key)
                if window.contains(paper.updated_at):
                    yield paper
            start += len(papers)
            if start >= total:
                return
            if start >= RESULT_LIMIT:
                raise SourceError("arXiv result limit reached; narrow the profile query")
