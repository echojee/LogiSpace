from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _TextHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "aside"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "aside"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


@dataclass(frozen=True)
class FrozenPage:
    snapshot_id: str
    url: str
    content_hash: str
    text: str


def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) URLs are allowed")
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError("Private, loopback, link-local, and reserved addresses are blocked")


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page(url: str, *, timeout: int = 20, max_bytes: int = 2_000_000) -> FrozenPage:
    _assert_public_http_url(url)
    response = build_opener(_SafeRedirectHandler()).open(Request(url, headers={"User-Agent": "LogiSpace/0.4"}), timeout=timeout)
    final_url = response.geturl()
    _assert_public_http_url(final_url)
    content_type = response.headers.get_content_type()
    if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
        raise ValueError(f"Unsupported MIME type: {content_type}")
    raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Response exceeds maximum retained size")
    parser = _TextHTML()
    parser.feed(raw.decode(response.headers.get_content_charset() or "utf-8", "replace"))
    text = "\n".join(parser.parts) if content_type != "text/plain" else raw.decode("utf-8", "replace")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return FrozenPage(f"snap_{digest[:16]}", final_url, digest, text)
