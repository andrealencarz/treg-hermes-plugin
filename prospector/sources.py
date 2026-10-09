"""Source adapters return one lead shape, independent of provider payloads."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SourceSpec:
    endpoint: str
    method: str
    estimate_micro: int
    result_key: str


SOURCES = {
    "google_maps": SourceSpec("anyapi.google.serp.maps", "POST", 10_000, "items"),
    "instagram": SourceSpec("scrapecreators.x.v1-instagram-search-profiles", "GET", 10_000, "profiles"),
    "linkedin": SourceSpec("harvestapi.linkedin.company.search", "GET", 10_000, "elements"),
}


def selected(value) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or x not in SOURCES for x in value):
        raise ValueError("Selecione ao menos uma fonte válida")
    return list(dict.fromkeys(value))


def _url(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    return value.strip() if parsed.scheme in ("http", "https") and parsed.hostname else None


def _text(value) -> str | None:
    value = str(value).strip() if value is not None else ""
    return value or None


def normalize(source: str, item: dict, *, city: str, uf: str, niche: str) -> dict | None:
    """Canonical lead: stable source ID, public evidence, business fields and search region."""
    if not isinstance(item, dict):
        return None
    if source == "google_maps":
        name, external_id = _text(item.get("name")), _text(item.get("placeId"))
        website, evidence = _url(item.get("website")), _url(item.get("url"))
        phone = _text(item.get("phone"))
    elif source == "instagram":
        username = (_text(item.get("username")) or "").lstrip("@").lower()
        name = _text(item.get("full_name")) or username
        external_id = username or _text(item.get("id"))
        evidence = _url(item.get("url")) or (_url(f"https://www.instagram.com/{username}/") if username else None)
        website = _url(item.get("external_url"))
        phone = None
    elif source == "linkedin":
        name = _text(item.get("name"))
        slug = _text(item.get("universalName"))
        external_id = slug or _text(item.get("id"))
        evidence = _url(item.get("linkedinUrl")) or (_url(f"https://www.linkedin.com/company/{slug}/") if slug else None)
        website = _url(item.get("website"))
        phone = None
    else:
        raise ValueError("Fonte desconhecida")
    if not name or not external_id:
        return None
    # Social profile URLs are evidence, never the company's website/domain.
    domain = urlsplit(website).hostname.lower() if website else None
    if domain and domain.startswith("www."):
        domain = domain[4:]
    phone_digits = "".join(c for c in phone if c.isdigit() or c == "+") if phone else ""
    return {"name": name, "niche": niche, "city": city, "uf": uf,
            "website": website, "domain": domain,
            "phone": phone_digits or None,
            "email": None, "source": source, "external_id": external_id,
            "evidence_url": evidence}
