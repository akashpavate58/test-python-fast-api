from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.core.config import AppSettings
from app.models.ingestion import CrawledPage, DiscoveredLink, ExtractedPageContent


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() not in {"a", "area", "link"}:
            return

        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


@dataclass(frozen=True)
class PageFetchResult:
    page_url: str
    final_url: str
    http_status: int
    content_type: Optional[str]
    content_length: Optional[int]
    html: Optional[str]
    fetched_at: datetime
    error: Optional[str]


@dataclass(frozen=True)
class CrawlOutcome:
    crawled_pages: list[CrawledPage]
    discovered_links: list[DiscoveredLink]


class _RedirectLimitHandler(HTTPRedirectHandler):
    def __init__(self, max_redirects: int) -> None:
        super().__init__()
        self.max_redirects = max_redirects

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirects = len(getattr(req, "redirect_dict", {}))
        if redirects >= self.max_redirects:
            raise HTTPError(
                req.full_url,
                code,
                "Maximum redirects exceeded",
                headers,
                fp,
            )

        request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if request is not None:
            redirect_dict = getattr(req, "redirect_dict", {})
            redirect_dict = dict(redirect_dict)
            redirect_dict[req.full_url] = True
            request.redirect_dict = redirect_dict
        return request


def _extract_links(html: str) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html)
    return parser.links


def _normalize_url(source_url: str, href: str) -> Optional[str]:
    try:
        resolved = urljoin(source_url, href.strip())
    except (ValueError, TypeError):
        return None

    stripped_url, _ = urldefrag(resolved)
    parsed = urlparse(stripped_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    path = parsed.path or "/"
    normalized = urlunparse(
        (scheme, parsed.netloc, path, "", parsed.query, "")
    )
    return normalized


def _is_html_content_type(content_type: Optional[str]) -> bool:
    if content_type is None:
        return False

    content_type_lower = content_type.split(";", 1)[0].strip().lower()
    return content_type_lower in {"text/html", "application/xhtml+xml"}


def _should_retry_fetch_result(result: PageFetchResult) -> bool:
    if result.html is not None:
        return False
    if result.http_status == 0:
        return True
    if result.http_status in {408, 429}:
        return True
    return 500 <= result.http_status < 600


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignore_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._ignore_depth += 1
            return
        if tag.lower() in {
            "p",
            "div",
            "br",
            "li",
            "section",
            "article",
            "header",
            "footer",
            "nav",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            self._append_whitespace()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"}:
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return
        if tag.lower() in {
            "p",
            "div",
            "br",
            "li",
            "section",
            "article",
            "header",
            "footer",
            "nav",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            self._append_whitespace()

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        self._chunks.append(data)

    def _append_whitespace(self) -> None:
        if self._chunks and not self._chunks[-1].endswith(" "):
            self._chunks.append(" ")

    def get_text(self) -> str:
        text = "".join(self._chunks)
        return " ".join(text.split())


def extract_text(html: str) -> str:
    extractor = HTMLTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.get_text()


def extract_page_content(
    submitted_url: str,
    page_fetch_result: PageFetchResult,
) -> ExtractedPageContent:
    html = page_fetch_result.html or ""
    text = extract_text(html) if html else ""
    return ExtractedPageContent(
        submitted_url=submitted_url,
        page_url=page_fetch_result.page_url,
        final_url=page_fetch_result.final_url,
        fetched_at=page_fetch_result.fetched_at,
        http_status=page_fetch_result.http_status,
        content_type=page_fetch_result.content_type,
        content_length=page_fetch_result.content_length,
        fetch_error=page_fetch_result.error,
        html=html,
        text=text,
        metadata={
            "final_url": page_fetch_result.final_url,
            "fetch_error": page_fetch_result.error,
            "content_type": page_fetch_result.content_type,
            "content_length": page_fetch_result.content_length,
        },
    )


def _allowed_schemes(settings: AppSettings) -> list[str]:
    schemes = settings.crawl_allowed_schemes
    if isinstance(schemes, str):
        return [schemes]
    return [scheme.lower() for scheme in schemes]


def _is_same_host(root_url: str, candidate_url: str) -> bool:
    return urlparse(root_url).netloc == urlparse(candidate_url).netloc


def _fetch_page_once(
    page_url: str,
    timeout_seconds: int,
    user_agent: str,
    max_redirects: int,
) -> PageFetchResult:
    request = Request(page_url, headers={"User-Agent": user_agent})
    opener = build_opener(_RedirectLimitHandler(max_redirects))

    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            content_type = response.headers.get("Content-Type")
            content_length_raw = response.headers.get("Content-Length")
            content_length = None
            if content_length_raw and content_length_raw.isdigit():
                content_length = int(content_length_raw)

            charset = response.headers.get_content_charset("utf-8")
            html = response.read().decode(charset, errors="replace")
            return PageFetchResult(
                page_url=page_url,
                final_url=response.geturl(),
                http_status=getattr(response, "status", response.getcode()),
                content_type=content_type,
                content_length=content_length,
                html=html,
                fetched_at=datetime.now(timezone.utc),
                error=None,
            )
    except HTTPError as exc:
        return PageFetchResult(
            page_url=page_url,
            final_url=getattr(exc, "url", page_url),
            http_status=exc.code,
            content_type=getattr(exc, "headers", {}).get("Content-Type") if exc.headers else None,
            content_length=None,
            html=None,
            fetched_at=datetime.now(timezone.utc),
            error=str(exc),
        )
    except URLError as exc:
        return PageFetchResult(
            page_url=page_url,
            final_url=page_url,
            http_status=0,
            content_type=None,
            content_length=None,
            html=None,
            fetched_at=datetime.now(timezone.utc),
            error=str(exc.reason) if hasattr(exc, "reason") else str(exc),
        )


def fetch_page(
    page_url: str,
    timeout_seconds: int,
    user_agent: str,
    max_redirects: int,
    max_retries: int = 0,
    retry_delay_seconds: int = 0,
) -> PageFetchResult:
    last_result: PageFetchResult | None = None
    for attempt in range(max_retries + 1):
        result = _fetch_page_once(
            page_url,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
            max_redirects=max_redirects,
        )
        if not _should_retry_fetch_result(result) or attempt >= max_retries:
            return result
        last_result = result
        time.sleep(retry_delay_seconds)
    return last_result or _fetch_page_once(
        page_url,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
        max_redirects=max_redirects,
    )


def crawl(
    submitted_url: str,
    settings: AppSettings,
    page_fetcher: Optional[Callable[[str], PageFetchResult]] = None,
) -> CrawlOutcome:
    root_url = _normalize_url(submitted_url, submitted_url)
    if root_url is None:
        raise ValueError("Submitted URL is invalid.")

    if page_fetcher is None:
        page_fetcher = lambda url: fetch_page(
            url,
            timeout_seconds=settings.crawl_request_timeout_seconds,
            user_agent=settings.crawl_user_agent,
            max_redirects=settings.crawl_max_redirects,
            max_retries=settings.crawl_request_max_retries,
            retry_delay_seconds=settings.crawl_request_retry_delay_seconds,
        )

    scheduled: list[tuple[str, int]] = [(root_url, 0)]
    scheduled_urls: set[str] = {root_url}
    discovered_links: list[DiscoveredLink] = []
    seen_links: set[str] = set()
    crawled_pages: list[CrawledPage] = []
    root_host = urlparse(root_url).netloc
    allowed_schemes = _allowed_schemes(settings)

    while scheduled and len(crawled_pages) < settings.crawl_max_pages_per_job:
        page_url, depth = scheduled.pop(0)
        page_fetch_result = page_fetcher(page_url)

        crawled_pages.append(
            CrawledPage(
                submitted_url=root_url,
                page_url=page_url,
                final_url=page_fetch_result.final_url,
                fetched_at=page_fetch_result.fetched_at,
                http_status=page_fetch_result.http_status,
                content_type=page_fetch_result.content_type,
                content_length=page_fetch_result.content_length,
                fetch_error=page_fetch_result.error,
            )
        )

        if page_fetch_result.html is None:
            continue

        if not _is_html_content_type(page_fetch_result.content_type):
            continue

        if depth >= settings.crawl_max_depth:
            continue

        for raw_link in _extract_links(page_fetch_result.html):
            normalized = _normalize_url(page_url, raw_link)
            if normalized is None:
                continue

            parsed = urlparse(normalized)
            if parsed.scheme.lower() not in allowed_schemes:
                continue

            if settings.crawl_same_host_only and root_host != parsed.netloc:
                continue

            if normalized in seen_links:
                continue

            if normalized not in scheduled_urls and len(scheduled_urls) < settings.crawl_max_pages_per_job:
                seen_links.add(normalized)
                scheduled.append((normalized, depth + 1))
                scheduled_urls.add(normalized)
                discovered_links.append(
                    DiscoveredLink(
                        submitted_url=root_url,
                        page_url=page_url,
                        link_url=normalized,
                    )
                )

    return CrawlOutcome(
        crawled_pages=crawled_pages,
        discovered_links=discovered_links,
    )
