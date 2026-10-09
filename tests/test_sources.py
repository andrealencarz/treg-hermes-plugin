import io
import json

import pytest

from prospector import treg
from prospector.service import DomainError, ProspectorService
from prospector.sources import SOURCES, normalize
from prospector.treg import TregResult
from prospector.worker import process_one


class Response:
    def __init__(self, body, cost="4000"):
        self.body = io.BytesIO(json.dumps(body).encode())
        self.headers = {"X-Treg-Call-Id": "remote-1", "X-Treg-Cost-Micro": cost}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def read(self, size=-1):
        return self.body.read(size)


def test_social_requests_and_provider_shapes(monkeypatch):
    seen = []

    def fake_open(request, timeout):
        seen.append(request)
        if "instagram" in request.full_url:
            return Response({"output": {"data": {"profiles": [{"username": "clinica.exemplo", "full_name": "Clínica Exemplo"}]}}}, "1880")
        return Response({"output": {"data": {"elements": [{"universalName": "clinica-exemplo", "name": "Clínica Exemplo"}]}}})

    monkeypatch.setattr(treg.urllib.request, "urlopen", fake_open)
    for source, key in (("instagram", "profiles"), ("linkedin", "elements")):
        result = treg.search_source(source=source, token="test", org=None, query="clínica", city="Fortaleza",
                                    uf="CE", limit=10, idempotency_key=source, max_cost_micro=10_000)
        assert len(result.items) == 1
        assert result.cost_micro in (1880, 4000)
        assert seen[-1].get_method() == "GET"
        assert "/call/" + SOURCES[source].endpoint in seen[-1].full_url
        assert seen[-1].headers["X-treg-route-max-cost"] == "0.010000"
    assert "query=cl%C3%ADnica+Fortaleza+CE" in seen[0].full_url
    assert "location=Fortaleza%2C+CE%2C+Brasil" in seen[1].full_url


def test_unknown_social_response_preserves_charge_for_reconciliation(monkeypatch):
    monkeypatch.setattr(treg.urllib.request, "urlopen", lambda *_args, **_kwargs: Response({"unexpected": []}))
    with pytest.raises(treg.TregError) as caught:
        treg.search_source(source="linkedin", token="test", org=None, query="dentista", city="Fortaleza",
                           uf="CE", limit=10, idempotency_key="idem", max_cost_micro=10_000)
    assert caught.value.cost_micro == 4000
    assert caught.value.call_id == "remote-1"


def test_normalized_leads_do_not_mistake_social_profile_for_company_site():
    instagram = normalize("instagram", {"username": "Clinica.Exemplo", "full_name": "Clínica Exemplo",
        "url": "https://www.instagram.com/clinica.exemplo/", "external_url": "https://clinica.example"},
        city="Fortaleza", uf="CE", niche="dentista")
    linkedin = normalize("linkedin", {"universalName": "clinica-exemplo", "name": "Clínica Exemplo",
        "linkedinUrl": "https://www.linkedin.com/company/clinica-exemplo/"},
        city="Fortaleza", uf="CE", niche="dentista")
    assert instagram["external_id"] == "clinica.exemplo"
    assert instagram["domain"] == "clinica.example"
    assert linkedin["website"] is None and linkedin["domain"] is None
    assert linkedin["evidence_url"].startswith("https://www.linkedin.com/company/")
    assert normalize("instagram", {"full_name": "Sem ID"}, city="Fortaleza", uf="CE", niche="x") is None


def test_multi_source_campaign_persists_selection_and_runs_each_source(tmp_path, monkeypatch):
    service = ProspectorService(tmp_path / "db.sqlite")
    monkeypatch.setattr(treg, "source_capability", lambda source: {
        "discovery": True, "platform_eligible": True, "blocked": None, "cost": {"usd": 0.004}})
    campaign = service.create_campaign(name="Clínicas", niche="dentista",
        cities=[{"city":"Fortaleza","uf":"CE"}], sources=["google_maps", "instagram", "linkedin"],
        run_cap_micro=30_000)
    assert campaign["sources"] == ["google_maps", "instagram", "linkedin"]
    service.enqueue(campaign["id"])
    monkeypatch.setattr(treg, "search_source", lambda source, **kwargs: TregResult(
        ([{"username":"clinica.exemplo", "full_name":"Clínica Exemplo", "external_url":"https://clinica.example"}]
         if source == "instagram" else
         [{"universalName":"clinica-exemplo", "name":"Clínica Exemplo", "website":"https://clinica.example"}]),
        "call-" + source, 4000))
    result = process_one(service, token="test", search=lambda **kwargs: TregResult(
        [{"placeId":"p1", "name":"Clínica Exemplo", "website":"https://clinica.example"}], "call-maps", 1750))
    assert result["state"] == "succeeded"
    assert result["cost_micro"] == 9750
    assert result["new_global"] == result["new_campaign"] == 1
    assert set(service.leads()["items"][0]["sources"]) == {"google_maps", "instagram", "linkedin"}
    assert {r["endpoint"] for r in service.conn.execute("SELECT endpoint FROM tool_call")} == {
        spec.endpoint for spec in SOURCES.values()}
    service.update_campaign(campaign["id"], sources=["instagram"])
    assert service.campaign(campaign["id"])["sources"] == ["instagram"]
    assert service.run(result["id"])["campaign_snapshot"]["sources"] == ["google_maps", "instagram", "linkedin"]
    with pytest.raises(DomainError, match="fonte"):
        service.update_campaign(campaign["id"], sources=[])
    service.close()


def test_catalog_price_above_call_limit_stops_before_paid_request(tmp_path, monkeypatch):
    service = ProspectorService(tmp_path / "budget.db")
    campaign = service.create_campaign(name="Teste", niche="dentista", cities=[{"city":"Fortaleza","uf":"CE"}],
                                       sources=["linkedin"], run_cap_micro=10_000)
    service.enqueue(campaign["id"])
    monkeypatch.setattr(treg, "source_capability", lambda source: {
        "discovery": True, "platform_eligible": True, "blocked": None, "cost": {"usd": 0.02}})
    monkeypatch.setattr(treg, "search_source", lambda **kwargs: pytest.fail("chamada paga não deveria ocorrer"))
    result = process_one(service, token="test")
    assert result["state"] == "failed"
    assert "excede" in result["error"]
    assert service.conn.execute("SELECT COUNT(*) FROM tool_call").fetchone()[0] == 0
    service.close()


def test_old_campaign_migrates_to_google_maps(tmp_path):
    path = tmp_path / "old.db"
    service = ProspectorService(path)
    campaign = service.create_campaign(name="Antiga", niche="dentista", cities=[{"city":"Fortaleza","uf":"CE"}])
    service.conn.execute("DELETE FROM schema_migration WHERE version=6")
    # Simulate an older installation by rebuilding just the campaign schema without the new column.
    service.conn.execute("ALTER TABLE campaign DROP COLUMN sources_json")
    service.close()
    migrated = ProspectorService(path)
    assert migrated.campaign(campaign["id"])["sources"] == ["google_maps"]
    assert migrated.conn.execute("SELECT MAX(version) FROM schema_migration").fetchone()[0] == 6
    migrated.close()
