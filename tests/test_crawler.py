from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import AppSettings
from app.services.crawler import CrawlOutcome, PageFetchResult, crawl, _normalize_url


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
