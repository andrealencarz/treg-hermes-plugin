import io
import json
from pathlib import Path

import pytest

from prospector import treg
from prospector.treg import TregError
from scripts import treg_smoke


class Response:
    def __init__(self, body, headers=None):
        self.stream = io.BytesIO(json.dumps(body).encode())
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.stream.close()

    def read(self, size=-1):
        return self.stream.read(size)


def test_search_request_contract_and_cost(monkeypatch):
    captured = {}

    def fake_open(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response({"output": {"data": {"items": [{"name": "Exemplo", "placeId": "p1"}]}}},
                        {"X-Treg-Call-Id": "call-1", "X-Treg-Cost-Micro": "1750"})

    monkeypatch.setattr(treg.urllib.request, "urlopen", fake_open)
    result = treg.search_maps(token="fake-secret", org="equipe", query="dentista", city="Fortaleza",
        uf="CE", limit=1, idempotency_key="idem-1", max_cost_micro=10_000, local_call_id="local-1")
    request = captured["request"]
    assert request.get_method() == "POST"
    assert request.full_url == "https://treg.to/call/anyapi.google.serp.maps"
    assert request.headers["X-treg-token"] == "fake-secret"
    assert request.headers["X-treg-org"] == "equipe"
    assert request.headers["X-treg-route-max-cost"] == "0.010000"
    assert request.headers["Idempotency-key"] == "idem-1"
    assert request.headers["X-treg-meta"] == "prospector_call=local-1"
    assert json.loads(request.data)["limit"] == 1
    assert result.cost_micro == 1750
    assert result.call_id == "call-1"
    assert len(result.items) == 1


def test_unexpected_shape_keeps_known_cost_for_reconciliation(monkeypatch):
    monkeypatch.setattr(treg.urllib.request, "urlopen", lambda *_args, **_kwargs:
                        Response({"output": {"data": {"items": "invalid"}}},
                                 {"X-Treg-Call-Id": "call-2", "X-Treg-Cost-Micro": "1750"}))
    with pytest.raises(TregError) as caught:
        treg.search_maps(token="fake", org=None, query="x", city="x", uf="CE", limit=1,
                         idempotency_key="idem", max_cost_micro=10_000)
    assert caught.value.call_id == "call-2"
    assert caught.value.cost_micro == 1750


def test_empty_treg_data_is_a_valid_zero_result(monkeypatch):
    monkeypatch.setattr(treg.urllib.request, "urlopen", lambda *_args, **_kwargs:
                        Response({"output": {"data": None, "found": 0}},
                                 {"X-Treg-Call-Id": "call-empty", "X-Treg-Cost-Micro": "1750"}))
    result = treg.search_maps(token="fake", org=None, query="x", city="x", uf="CE", limit=1,
                              idempotency_key="idem", max_cost_micro=10_000)
    assert result.items == []
    assert result.cost_micro == 1750


def test_token_file_requires_private_permissions_and_paid_state_is_unique(tmp_path: Path):
    token = tmp_path / "token"
    token.write_text("fake-token\n")
    token.chmod(0o644)
    with pytest.raises(ValueError, match="permissão"):
        treg_smoke.private_token(token)
    token.chmod(0o600)
    assert treg_smoke.private_token(token) == "fake-token"
    env_file = tmp_path / ".env"
    env_file.write_text("TREG_TOKEN=fake-token\nTREG_ORG=equipe\n")
    env_file.chmod(0o600)
    assert treg_smoke.private_credentials(env_file) == ("fake-token", "equipe")
    with pytest.raises(ValueError):
        treg_smoke.micro_usd("0.20")
    assert treg_smoke.micro_usd("0.01") == 10_000
    state = treg_smoke.new_state_dir(tmp_path / "paid-attempt")
    with pytest.raises(FileExistsError):
        treg_smoke.new_state_dir(state)


def test_paid_smoke_uses_one_local_call_and_persists_audit(tmp_path: Path, monkeypatch):
    from prospector.treg import TregResult
    from prospector.worker import process_one

    def fake_search(**kwargs):
        assert kwargs["max_cost_micro"] == 5000
        assert kwargs["limit"] == 1
        return TregResult([{"name": "Clínica Exemplo", "placeId": "p1"}], "call-1", 1750)

    monkeypatch.setattr(treg_smoke, "process_one", lambda service, token, search:
                        process_one(service, token=token, search=fake_search))
    result = treg_smoke.paid_once("fake-token", None, 5000, tmp_path / "attempt")
    assert result["attempted_calls"] == 1
    assert result["cost_micro"] == 1750
    assert result["leads"] == 1
    assert json.loads((tmp_path / "attempt" / "attempt.json").read_text()) == result
    assert "fake-token" not in (tmp_path / "attempt" / "attempt.json").read_text()


def test_catalog_example_is_a_single_bounded_request(tmp_path: Path, monkeypatch):
    from prospector.treg import TregResult
    calls = []

    def fake_search(**kwargs):
        calls.append(kwargs)
        return TregResult([], "call-1", 1750, {"found": False})

    monkeypatch.setattr(treg_smoke.treg, "search_maps", fake_search)
    result = treg_smoke.catalog_example_once("fake-token", "equipe", 10_000, tmp_path / "catalog")
    assert len(calls) == 1
    assert calls[0]["location_override"] == "Austin, TX"
    assert calls[0]["language"] is None
    assert calls[0]["max_cost_micro"] == 10_000
    assert result["cost_micro"] == 1750
    assert "fake-token" not in (tmp_path / "catalog" / "attempt.json").read_text()
