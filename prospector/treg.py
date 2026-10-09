from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .sources import SOURCES, normalize

ENDPOINT = "anyapi.google.serp.maps"
BASE_URL = "https://treg.to"


@dataclass(frozen=True)
class TregResult:
    items: list[dict]
    call_id: str | None
    cost_micro: int | None
    diagnostic: dict | None = None


class TregError(Exception):
    def __init__(self, message: str, *, call_id: str | None = None, cost_micro: int | None = None):
        super().__init__(message)
        self.call_id = call_id
        self.cost_micro = cost_micro


def _cost(headers) -> int | None:
    raw = headers.get("X-Treg-Cost-Micro")
    if raw is None:
        return None
    try:
        value = int(raw)
        return value if value >= 0 else None
    except ValueError:
        return None


def validate_token(token: str, org: str | None = None) -> dict:
    headers = {"X-Treg-Token": token}
    if org:
        headers["X-Treg-Org"] = org
    request = urllib.request.Request(BASE_URL + "/auth/me", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise TregError("Chave Treg inválida ou sem acesso à organização") from exc
        raise TregError(f"Validação Treg indisponível (HTTP {exc.code})") from exc
    except urllib.error.URLError as exc:
        raise TregError("Falha de rede ao validar o Treg; a chave anterior foi preservada") from exc


def catalog_capability() -> dict:
    """Consulta pública e gratuita para validar o contrato do adaptador escolhido."""
    request = urllib.request.Request(BASE_URL + "/catalog/endpoints/" + ENDPOINT)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TregError("Catálogo Treg indisponível") from exc
    endpoint = body.get("endpoint", {})
    inputs = endpoint.get("input", {}).get("body", {})
    usable = endpoint.get("method") == "POST" and all(key in inputs for key in ("query", "location", "limit"))
    return {"source": "google_maps", "endpoint": ENDPOINT, "discovery": usable,
            "platform_eligible": endpoint.get("platform_eligible"), "cost": endpoint.get("cost"),
            "blocked": endpoint.get("platform_blocked")}


def source_capability(source: str) -> dict:
    spec = SOURCES[source]
    if source == "google_maps":
        return catalog_capability()
    request = urllib.request.Request(BASE_URL + "/catalog/endpoints/" + spec.endpoint)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            endpoint = json.load(response).get("endpoint", {})
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise TregError("Catálogo Treg indisponível") from exc
    params = endpoint.get("input", {}).get("queryParams", {})
    required = "query" if source == "instagram" else "search"
    return {"source": source, "endpoint": spec.endpoint,
            "discovery": endpoint.get("method") == spec.method and required in params,
            "platform_eligible": endpoint.get("platform_eligible"),
            "blocked": endpoint.get("platform_blocked"), "cost": endpoint.get("cost")}


def _source_items(body: dict, source: str, *, call_id: str | None, cost_micro: int | None) -> list[dict]:
    spec = SOURCES[source]
    candidates = [body]
    for key in ("output", "data", "body"):
        for node in tuple(candidates):
            if isinstance(node, dict) and isinstance(node.get(key), dict):
                candidates.append(node[key])
    for node in candidates:
        if not isinstance(node, dict):
            continue
        if node.get("success") is False or node.get("error") or str(node.get("status") or "").lower() in ("error", "failed"):
            raise TregError(f"Busca {source} falhou no provedor", call_id=call_id, cost_micro=cost_micro)
        if spec.result_key in node:
            items = node[spec.result_key]
            if isinstance(items, list) and all(isinstance(x, dict) for x in items):
                return items
            raise TregError(f"Resultados {source} em formato inesperado", call_id=call_id, cost_micro=cost_micro)
    raise TregError(f"Resultados {source} ausentes na resposta", call_id=call_id, cost_micro=cost_micro)


def search_source(*, source: str, token: str, org: str | None, query: str, city: str, uf: str,
                  limit: int, idempotency_key: str, max_cost_micro: int,
                  local_call_id: str | None = None) -> TregResult:
    if source == "google_maps":
        return search_maps(token=token, org=org, query=query, city=city, uf=uf, limit=limit,
                           idempotency_key=idempotency_key, max_cost_micro=max_cost_micro,
                           local_call_id=local_call_id)
    if source not in SOURCES or max_cost_micro <= 0:
        raise ValueError("Fonte ou teto por chamada inválido")
    spec = SOURCES[source]
    params = {"query": f"{query} {city} {uf}"} if source == "instagram" else {
        "search": query, "location": f"{city}, {uf}, Brasil", "page": 1}
    url = BASE_URL + "/call/" + spec.endpoint + "?" + urllib.parse.urlencode(params)
    headers = {"X-Treg-Token": token, "Idempotency-Key": idempotency_key,
               "X-Treg-Route-Max-Cost": f"{max_cost_micro / 1_000_000:.6f}"}
    if org:
        headers["X-Treg-Org"] = org
    if local_call_id:
        headers["X-Treg-Meta"] = f"prospector_call={local_call_id}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=spec.method), timeout=100) as response:
            call_id, cost_micro = response.headers.get("X-Treg-Call-Id"), _cost(response.headers)
            try:
                body = json.load(response)
            except (ValueError, UnicodeDecodeError) as exc:
                raise TregError("Resposta JSON do Treg inválida", call_id=call_id, cost_micro=cost_micro) from exc
    except urllib.error.HTTPError as exc:
        raise TregError(f"Treg retornou HTTP {exc.code}", call_id=exc.headers.get("X-Treg-Call-Id"),
                        cost_micro=_cost(exc.headers)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TregError("Resposta do Treg não recebida; a cobrança precisa de reconciliação") from exc
    if not isinstance(body, dict):
        raise TregError("Resposta do Treg em formato inesperado", call_id=call_id, cost_micro=cost_micro)
    items = _source_items(body, source, call_id=call_id, cost_micro=cost_micro)
    return TregResult(items=items[:limit], call_id=call_id, cost_micro=cost_micro,
                      diagnostic={"items_returned": len(items), "source": source})


def search_maps(*, token: str, org: str | None, query: str, city: str, uf: str,
                limit: int, idempotency_key: str, max_cost_micro: int,
                local_call_id: str | None = None, location_override: str | None = None,
                language: str | None = "pt") -> TregResult:
    if not 1 <= limit <= 20:
        raise ValueError("O adaptador Google Maps aceita 1 a 20 resultados")
    if max_cost_micro <= 0:
        raise ValueError("Teto por chamada precisa ser positivo")
    body = {"query": query, "location": location_override or f"{city}, {uf}, Brasil", "limit": limit}
    if language:
        body["language"] = language
    payload = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Treg-Token": token,
               "Idempotency-Key": idempotency_key,
               "X-Treg-Route-Max-Cost": f"{max_cost_micro / 1_000_000:.6f}"}
    if org:
        headers["X-Treg-Org"] = org
    if local_call_id:
        headers["X-Treg-Meta"] = f"prospector_call={local_call_id}"
    request = urllib.request.Request(BASE_URL + "/call/" + ENDPOINT, payload, headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=100) as response:
            call_id = response.headers.get("X-Treg-Call-Id")
            cost_micro = _cost(response.headers)
            try:
                body = json.load(response)
            except (ValueError, UnicodeDecodeError) as exc:
                raise TregError("Resposta JSON do Treg inválida", call_id=call_id,
                                cost_micro=cost_micro) from exc
    except urllib.error.HTTPError as exc:
        raise TregError(f"Treg retornou HTTP {exc.code}", call_id=exc.headers.get("X-Treg-Call-Id"),
                        cost_micro=_cost(exc.headers)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TregError("Resposta do Treg não recebida; a cobrança precisa de reconciliação") from exc
    if not isinstance(body, dict):
        raise TregError("Resposta do Treg em formato inesperado", call_id=call_id, cost_micro=cost_micro)
    output = body.get("output")
    data = output.get("data") if isinstance(output, dict) else None
    items = data.get("items", []) if isinstance(data, dict) else []
    if items is None:
        items = []
    if not isinstance(items, list):
        raise TregError("Resposta do Treg em formato inesperado", call_id=call_id, cost_micro=cost_micro)
    diagnostic = {"root_keys": sorted(body.keys()),
                  "output_type": type(output).__name__, "data_type": type(data).__name__,
                  "data_keys": sorted(data.keys()) if isinstance(data, dict) else [],
                  "found": output.get("found") if isinstance(output, dict) and
                           isinstance(output.get("found"), int) else None,
                  "items_returned": len(items),
                  "items_with_place_id": sum(isinstance(item, dict) and bool(item.get("placeId")) for item in items)}
    return TregResult(items=items, call_id=call_id, cost_micro=cost_micro, diagnostic=diagnostic)


def _read_json(path: str, *, token: str, org: str | None):
    headers = {"X-Treg-Token": token}
    if org:
        headers["X-Treg-Org"] = org
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE_URL + path, headers=headers), timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise TregError(f"Consulta de histórico Treg falhou (HTTP {exc.code})") from exc
    except urllib.error.URLError as exc:
        raise TregError("Histórico Treg indisponível pela rede") from exc


def get_call(*, token: str, org: str | None, call_id: str) -> dict:
    return _read_json("/calls/" + urllib.parse.quote(call_id, safe=""), token=token, org=org)


def find_call(*, token: str, org: str | None, local_call_id: str) -> str | None:
    """Busca uma auditoria recente por tag; ausência não prova ausência de cobrança."""
    before = None
    for _ in range(4):
        suffix = f"&before_id={before}" if before else ""
        rows = _read_json(f"/calls?limit=500&days=30{suffix}", token=token, org=org)
        if not isinstance(rows, list):
            return None
        for row in rows:
            tags = row.get("tags") or {}
            if isinstance(tags, dict) and tags.get("prospector_call") == local_call_id:
                return row.get("call_ref")
        if len(rows) < 500:
            break
        before = rows[-1].get("id")
        if not isinstance(before, int):
            break
    return None


def normalize_place(item: dict, *, city: str, uf: str, niche: str) -> dict | None:
    return normalize("google_maps", item, city=city, uf=uf, niche=niche)
