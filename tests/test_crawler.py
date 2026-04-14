from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import AppSettings
from app.services.crawler import (
    CrawlOutcome,
    PageFetchResult,
    crawl,
    extract_page_content,
    extract_text,
    fetch_page,
    _normalize_url,
)


def make_fetch_result(
    page_url: str,
    html: str | None = None,
    content_type: str | None = "text/html; charset=utf-8",
    http_status: int = 200,
    error: str | None = None,
) -> PageFetchResult:
    return PageFetchResult(
        page_url=page_url,
        final_url=page_url,
        http_status=http_status,
        content_type=content_type,
        content_length=len(html) if html is not None else None,
        html=html,
        fetched_at=datetime.now(timezone.utc),
        error=error,
    )


def test_normalize_url_resolves_relative_links() -> None:
    normalized = _normalize_url("https://example.com/folder/", "../page.html")
    assert normalized == "https://example.com/page.html"


def test_normalize_url_preserves_absolute_links() -> None:
    normalized = _normalize_url("https://example.com/", "https://example.com/other")
    assert normalized == "https://example.com/other"


def test_normalize_url_removes_fragments() -> None:
    normalized = _normalize_url("https://example.com/", "https://example.com/page#section")
    assert normalized == "https://example.com/page"


def test_duplicate_links_are_suppressed() -> None:
    settings = AppSettings(
        crawl_max_depth=2,
        crawl_max_pages_per_job=10,
        crawl_request_timeout_seconds=1,
        crawl_max_redirects=5,
        crawl_same_host_only=True,
        crawl_allowed_schemes=["https"],
        crawl_user_agent="test-agent",
    )

    def fetcher(url: str) -> PageFetchResult:
        if url == "https://example.com/":
            return make_fetch_result(
                url,
                html="<a href=\"/page\">link</a><a href=\"/page\">duplicate</a>",
            )
        return make_fetch_result(url, html="", content_type="text/html")

    outcome = crawl("https://example.com/", settings, page_fetcher=fetcher)
    assert len(outcome.discovered_links) == 1
    assert str(outcome.discovered_links[0].link_url) == "https://example.com/page"
    assert len(outcome.crawled_pages) == 2


def test_same_host_filtering_respects_configuration() -> None:
    settings = AppSettings(
        crawl_max_depth=2,
        crawl_max_pages_per_job=10,
        crawl_request_timeout_seconds=1,
        crawl_max_redirects=5,
        crawl_same_host_only=True,
        crawl_allowed_schemes=["https"],
        crawl_user_agent="test-agent",
    )

    def fetcher(url: str) -> PageFetchResult:
        if url == "https://example.com/":
            return make_fetch_result(
                url,
                html="<a href=\"https://other.example.com/page\">external</a>",
            )
        return make_fetch_result(url, html="", content_type="text/html")

    outcome = crawl("https://example.com/", settings, page_fetcher=fetcher)
    assert not outcome.discovered_links
    assert len(outcome.crawled_pages) == 1


def test_max_depth_enforcement_stops_nested_discovery() -> None:
    settings = AppSettings(
        crawl_max_depth=1,
        crawl_max_pages_per_job=10,
        crawl_request_timeout_seconds=1,
        crawl_max_redirects=5,
        crawl_same_host_only=True,
        crawl_allowed_schemes=["https"],
        crawl_user_agent="test-agent",
    )

    def fetcher(url: str) -> PageFetchResult:
        if url == "https://example.com/":
            return make_fetch_result(
                url,
                html="<a href=\"/page1\">page1</a>",
            )
        if url == "https://example.com/page1":
            return make_fetch_result(
                url,
                html="<a href=\"/page2\">page2</a>",
            )
        return make_fetch_result(url, html="", content_type="text/html")

    outcome = crawl("https://example.com/", settings, page_fetcher=fetcher)
    assert {str(page.page_url) for page in outcome.crawled_pages} == {
        "https://example.com/",
        "https://example.com/page1",
    }
    assert not any(str(link.link_url) == "https://example.com/page2" for link in outcome.discovered_links)


def test_max_pages_enforcement_limits_queue_size() -> None:
    settings = AppSettings(
        crawl_max_depth=2,
        crawl_max_pages_per_job=2,
        crawl_request_timeout_seconds=1,
        crawl_max_redirects=5,
        crawl_same_host_only=True,
        crawl_allowed_schemes=["https"],
        crawl_user_agent="test-agent",
    )

    def fetcher(url: str) -> PageFetchResult:
        if url == "https://example.com/":
            return make_fetch_result(
                url,
                html="<a href=\"/page1\">page1</a><a href=\"/page2\">page2</a>",
            )
        return make_fetch_result(url, html="", content_type="text/html")

    outcome = crawl("https://example.com/", settings, page_fetcher=fetcher)
    assert len(outcome.crawled_pages) == 2
    assert len(outcome.discovered_links) == 1
    assert any(str(page.page_url) == "https://example.com/page1" for page in outcome.crawled_pages)
    assert not any(str(page.page_url) == "https://example.com/page2" for page in outcome.crawled_pages)


def test_non_html_pages_are_ignored_for_discovery() -> None:
    settings = AppSettings(
        crawl_max_depth=2,
        crawl_max_pages_per_job=10,
        crawl_request_timeout_seconds=1,
        crawl_max_redirects=5,
        crawl_same_host_only=True,
        crawl_allowed_schemes=["https"],
        crawl_user_agent="test-agent",
    )

    def fetcher(url: str) -> PageFetchResult:
        return make_fetch_result(
            url,
            html="%PDF-1.4\n%EOF",
            content_type="application/pdf",
        )

    outcome = crawl("https://example.com/", settings, page_fetcher=fetcher)
    assert len(outcome.crawled_pages) == 1
    assert not outcome.discovered_links


def test_crawl_records_fetch_failures_without_stopping() -> None:
    settings = AppSettings(
        crawl_max_depth=2,
        crawl_max_pages_per_job=10,
        crawl_request_timeout_seconds=1,
        crawl_max_redirects=5,
        crawl_same_host_only=True,
        crawl_allowed_schemes=["https"],
        crawl_user_agent="test-agent",
    )

    def fetcher(url: str) -> PageFetchResult:
        return make_fetch_result(url, html=None, http_status=0, error="timeout")

    outcome = crawl("https://example.com/", settings, page_fetcher=fetcher)

    assert len(outcome.crawled_pages) == 1
    assert outcome.crawled_pages[0].fetch_error == "timeout"
    assert outcome.crawled_pages[0].http_status == 0
    assert not outcome.discovered_links


def test_extract_text_removes_scripts_and_styles() -> None:
    html = """
        <html>
            <head>
                <style>body { color: red; }</style>
                <script>console.log('hi');</script>
            </head>
            <body>
                <p>Hello <strong>world</strong></p>
                <div>More text</div>
            </body>
        </html>
    """
    extracted = extract_text(html)

    assert extracted == "Hello world More text"


def test_extract_text_returns_minimal_text_for_sparse_pages() -> None:
    html = "<html><body><h1>Title</h1><p></p></body></html>"
    assert extract_text(html) == "Title"


def test_extract_page_content_includes_fetch_metadata() -> None:
    fetch_result = make_fetch_result(
        "https://example.com/page",
        html="<p>Example</p>",
        http_status=200,
    )
    extracted = extract_page_content("https://example.com", fetch_result)

    assert str(extracted.submitted_url) == "https://example.com/"
    assert str(extracted.page_url) == "https://example.com/page"
    assert str(extracted.final_url) == "https://example.com/page"
    assert extracted.http_status == 200
    assert extracted.text == "Example"
    assert extracted.metadata["final_url"] == "https://example.com/page"


def test_fetch_page_returns_redirected_final_url(monkeypatch) -> None:
    class StubHeaders(dict):
        def get_content_charset(self, default: str = "utf-8") -> str:
            return "utf-8"

    class StubResponse:
        def __init__(self) -> None:
            self.headers = StubHeaders({"Content-Type": "text/html; charset=utf-8", "Content-Length": "13"})

        def __enter__(self) -> "StubResponse":
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            pass

        def read(self) -> bytes:
            return b"<p>Redirected</p>"

        def geturl(self) -> str:
            return "https://example.com/redirected"

        def getcode(self) -> int:
            return 200

    class StubOpener:
        def open(self, request, timeout: int):
            return StubResponse()

    monkeypatch.setattr("app.services.crawler.build_opener", lambda handler: StubOpener())
    result = fetch_page(
        "https://example.com",
        timeout_seconds=1,
        user_agent="test-agent",
        max_redirects=5,
    )

    assert result.final_url == "https://example.com/redirected"
    assert result.http_status == 200
    assert result.html == "<p>Redirected</p>"


def test_fetch_page_retries_transient_failures(monkeypatch) -> None:
    calls: list[int] = []

    def stub_fetch(
        page_url: str,
        timeout_seconds: int,
        user_agent: str,
        max_redirects: int,
    ) -> PageFetchResult:
        calls.append(1)
        if len(calls) == 1:
            return PageFetchResult(
                page_url=page_url,
                final_url=page_url,
                http_status=0,
                content_type=None,
                content_length=None,
                html=None,
                fetched_at=datetime.now(timezone.utc),
                error="temporary failure",
            )
        return PageFetchResult(
            page_url=page_url,
            final_url=page_url,
            http_status=200,
            content_type="text/html; charset=utf-8",
            content_length=13,
            html="<p>Success</p>",
            fetched_at=datetime.now(timezone.utc),
            error=None,
        )

    monkeypatch.setattr("app.services.crawler._fetch_page_once", stub_fetch)
    result = fetch_page(
        "https://example.com",
        timeout_seconds=1,
        user_agent="test-agent",
        max_redirects=5,
        max_retries=1,
        retry_delay_seconds=0,
    )

    assert len(calls) == 2
    assert result.http_status == 200
    assert result.html == "<p>Success</p>"
