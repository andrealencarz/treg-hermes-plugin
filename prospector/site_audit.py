"""Small, bounded website audit using public HTML and no paid provider."""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit


MAX_HTML_BYTES = 512_000
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 5

KNOWN_HOSTS = {
    "linktr.ee": ("links", "Linktree"),
    "beacons.ai": ("links", "Beacons"),
    "bio.site": ("links", "Bio Site"),
    "taplink.cc": ("links", "Taplink"),
    "lnk.bio": ("links", "Lnk.Bio"),
    "msha.ke": ("links", "Milkshake"),
    "solo.to": ("links", "Solo"),
    "campsite.bio": ("links", "Campsite"),
    "flow.page": ("links", "Flowpage"),
    "many.link": ("links", "Manylink"),
    "bento.me": ("links", "Bento"),
    "myurls.co": ("links", "MyURLs"),
    "ifood.com.br": ("delivery", "iFood"),
    "aiqfome.com": ("delivery", "aiqfome"),
    "anota.ai": ("delivery", "Anota AI"),
    "menudino.com": ("delivery", "MenuDino"),
    "mercadolivre.com.br": ("marketplace", "Mercado Livre"),
    "shopee.com.br": ("marketplace", "Shopee"),
    "olx.com.br": ("marketplace", "OLX"),
    "instagram.com": ("social", "Instagram"),
    "facebook.com": ("social", "Facebook"),
    "wa.me": ("messaging", "WhatsApp"),
    "api.whatsapp.com": ("messaging", "WhatsApp"),
}


class UnsafeSite(ValueError):
    pass


def _host_type(host: str) -> tuple[str, str | None]:
    host = host.lower().removeprefix("www.")
    for domain, kind in KNOWN_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return kind
    return "website", None


def _safe_target(url: str) -> tuple[str, int, str, str]:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeSite("Endereço inválido") from exc
    if parsed.scheme not in {"https", "http"} or not host or parsed.username or parsed.password:
        raise UnsafeSite("Somente sites HTTP(S) públicos podem ser analisados")
    if port not in {80, 443} or "." not in host or host.endswith((".local", ".internal", ".localhost")):
        raise UnsafeSite("Endereço não público")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise UnsafeSite("Endereços IP não podem ser analisados")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except (OSError, UnicodeError) as exc:
        raise ConnectionError("DNS indisponível") from exc
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise UnsafeSite("Endereço não público")
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return host, port, sorted(addresses)[0], path


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, ip: str):
        super().__init__(host, port, timeout=TIMEOUT_SECONDS)
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, ip: str):
        super().__init__(host, port, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def fetch_html(url: str) -> tuple[int, str, str | None, str]:
    """Return HTTP status, final URL, content type and bounded HTML text."""
    for _ in range(MAX_REDIRECTS + 1):
        host, port, ip, path = _safe_target(url)
        parsed = urlsplit(url)
        connection = (_PinnedHTTPS if parsed.scheme == "https" else _PinnedHTTP)(host, port, ip)
        try:
            connection.request("GET", path, headers={"Host": host, "User-Agent": "HermesProspectorSiteAudit/1.0",
                "Accept": "text/html,application/xhtml+xml", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            status = response.status
            if status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    return status, url, None, ""
                url = urljoin(url, location)
                continue
            content_type = response.getheader("Content-Type", "").lower()
            if "html" not in content_type or response.getheader("Content-Encoding", "identity").lower() != "identity":
                return status, url, content_type, ""
            body = response.read(MAX_HTML_BYTES + 1)
            if len(body) > MAX_HTML_BYTES:
                body = body[:MAX_HTML_BYTES]
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip().strip('"')
            try:
                html = body.decode(charset, errors="replace")
            except LookupError:
                html = body.decode("utf-8", errors="replace")
            return status, url, content_type, html
        finally:
            connection.close()
    raise ConnectionError("Redirecionamentos em excesso")


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.h1 = 0
        self.noindex = False
        self.canonical = False
        self.lang = False
        self.viewport = False
        self.links: set[str] = set()
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = bool(attrs.get("lang"))
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta":
            name = (attrs.get("name") or "").lower()
            if name == "description":
                self.description = attrs.get("content") or ""
            elif name == "robots" and "noindex" in (attrs.get("content") or "").lower():
                self.noindex = True
            elif name == "viewport":
                self.viewport = True
        elif tag == "link" and "canonical" in (attrs.get("rel") or "").lower().split():
            self.canonical = bool(attrs.get("href"))
        elif tag == "a" and attrs.get("href"):
            self.links.add(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def analyze(url: str, fetcher=fetch_html) -> dict:
    """Classify availability and observable SEO signals, without claiming search ranking."""
    if not url:
        return {"availability": "no_site", "page_type": "unknown", "provider": None,
                "seo_score": None, "issues": ["Lead sem site informado"], "http_status": None, "final_url": None}
    try:
        input_kind, input_provider = _host_type(urlsplit(url).hostname or "")
    except ValueError:
        return {"availability": "unsafe", "page_type": "unknown", "provider": None,
                "seo_score": None, "issues": ["Endereço inválido"], "http_status": None, "final_url": None}
    try:
        status, final_url, content_type, html = fetcher(url)
    except UnsafeSite:
        return {"availability": "unsafe", "page_type": "unknown", "provider": None,
                "seo_score": None, "issues": ["Endereço não público ou inválido"], "http_status": None, "final_url": None}
    except (OSError, ConnectionError, TimeoutError, ssl.SSLError) as exc:
        return {"availability": "offline", "page_type": input_kind, "provider": input_provider,
                "seo_score": None, "issues": [type(exc).__name__], "http_status": None, "final_url": None}
    kind, provider = _host_type(urlsplit(final_url).hostname or "")
    final_parts = urlsplit(final_url)
    public_final_url = urlunsplit((final_parts.scheme, final_parts.netloc, final_parts.path, "", ""))
    result = {"availability": "online" if 200 <= status < 300 else "blocked" if status in {401, 403, 429}
              else "offline" if status >= 500 else "error", "page_type": kind, "provider": provider,
              "seo_score": None, "issues": [], "http_status": status, "final_url": public_final_url}
    if result["availability"] != "online":
        result["issues"] = [f"HTTP {status}"]
        return result
    if kind != "website":
        result["issues"] = ["Página em plataforma de terceiros; SEO do site próprio não aplicável"]
        return result
    if not html:
        result["issues"] = ["Conteúdo HTML indisponível para avaliar SEO"]
        return result
    page = _Page()
    page.feed(html)
    issues = []
    score = 100
    if not page.title.strip():
        issues.append("Sem título de página")
        score -= 25
    if not page.description.strip():
        issues.append("Sem meta description")
        score -= 20
    if not page.h1:
        issues.append("Sem título H1")
        score -= 15
    if page.noindex:
        issues.append("Página marcada como noindex")
        score -= 40
    if not page.canonical:
        issues.append("Sem URL canônica")
        score -= 10
    if not page.lang:
        issues.append("Idioma HTML não definido")
        score -= 5
    if not page.viewport:
        issues.append("Sem viewport para dispositivos móveis")
        score -= 5
    host = urlsplit(final_url).hostname or ""
    external = {urlsplit(urljoin(final_url, link)).hostname for link in page.links
                if urlsplit(urljoin(final_url, link)).hostname not in {None, host}}
    if len(external) >= 5 and page.h1 <= 1 and len(html) < 30_000:
        result["page_type"] = "possible_links"
        issues.append("Página parece reunir links externos; classificação a confirmar")
        result["seo_score"] = None
    else:
        result["seo_score"] = max(0, score)
    result["issues"] = issues
    return result
