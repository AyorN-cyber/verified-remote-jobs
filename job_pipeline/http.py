from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "VerifiedJobsPipeline/0.1 "
    "(open-source job verification; contact: local-user)"
)


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    ok: bool
    text: str
    html: str = ""
    title: str = ""
    error: str = ""


def fetch_page(url: str, timeout: int = 25) -> FetchResult:
    if not url:
        return FetchResult(url, "", 0, False, "", error="empty url")
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*"},
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return FetchResult(url, url, 0, False, "", error=str(exc))

    content_type = response.headers.get("content-type", "")
    raw_text = response.text if "text" in content_type or "json" in content_type or not content_type else response.text
    title = ""
    plain_text = raw_text
    if "<html" in raw_text.lower():
        soup = BeautifulSoup(raw_text, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        plain_text = soup.get_text(" ", strip=True)
    return FetchResult(
        url=url,
        final_url=response.url,
        status_code=response.status_code,
        ok=200 <= response.status_code < 400,
        text=plain_text,
        html=raw_text,
        title=title,
        error="" if 200 <= response.status_code < 400 else response.reason,
    )


def same_registered_domain(url_a: str, url_b: str) -> bool:
    host_a = urlparse(url_a).hostname or ""
    host_b = urlparse(url_b).hostname or ""
    if not host_a or not host_b:
        return False
    parts_a = host_a.lower().split(".")
    parts_b = host_b.lower().split(".")
    return ".".join(parts_a[-2:]) == ".".join(parts_b[-2:])
