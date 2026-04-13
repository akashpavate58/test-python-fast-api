from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.core.config import AppSettings
from app.models.ingestion import CrawledPage, DiscoveredLink


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


def _allowed_schemes(settings: AppSettings) -> list[str]:
    schemes = settings.crawl_allowed_schemes
    if isinstance(schemes, str):
        return [schemes]
    return [scheme.lower() for scheme in schemes]


def _is_same_host(root_url: str, candidate_url: str) -> bool:
    return urlparse(root_url).netloc == urlparse(candidate_url).netloc


def fetch_page(
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
            error=str(exc.reason) if hasattr(exc, "reason") else str(exc),
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
                fetched_at=datetime.now(timezone.utc),
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
