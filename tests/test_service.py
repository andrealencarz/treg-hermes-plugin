from pathlib import Path

import pytest

from prospector.service import DomainError, ProspectorService
from prospector.treg import TregError, TregResult
from prospector.worker import process_one


@pytest.fixture
def service(tmp_path: Path):
    instance = ProspectorService(tmp_path / "prospector.db")
    yield instance
    instance.close()


def campaign(service, name="Odonto"):
    return service.create_campaign(name=name, niche="clínica odontológica",
        cities=[{"city": "Fortaleza", "uf": "CE"}], run_cap_micro=10_000)


def place():
    return {"name": "Clínica Exemplo", "placeId": "ChIJ-EXAMPLE", "phone": "+55 85 3000-0000",
            "website": "https://clinica.example", "url": "https://maps.google.com/example"}


def test_worker_keeps_budget_and_business_status(service):
    first = campaign(service)
    run = service.enqueue(first["id"])
    with pytest.raises(DomainError, match="pendente"):
        service.enqueue(first["id"])

    def fake_search(**kwargs):
        assert kwargs["max_cost_micro"] == 10_000
        return TregResult([place()], "call-1", 1_750)

    result = process_one(service, token="test-only", search=fake_search)
    assert result["state"] == "succeeded"
    assert result["cost_micro"] == 1_750
    assert result["new_global"] == result["new_campaign"] == 1
    lead_id = service.leads()["items"][0]["id"]
    service.conn.execute("UPDATE lead SET status='Contatado' WHERE id=?", (lead_id,))
    second = campaign(service, "Outros serviços")
    service.enqueue(second["id"])
    result2 = process_one(service, token="test-only", search=fake_search)
    assert result2["new_global"] == 0
    assert result2["new_campaign"] == 1
    assert service.leads()["items"][0]["status"] == "Contatado"
    assert service.leads()["total"] == 1
    assert service.leads(campaign_id=second["id"])["total"] == 1


def test_global_budget_is_reserved_before_calls(service):
    one = campaign(service)
    two = campaign(service, "Outra")
    service.conn.execute("UPDATE workspace_settings SET global_monthly_cap_micro=10000 WHERE id=1")
    a = service.enqueue(one["id"])
    b = service.enqueue(two["id"])
    service.claim()
    hold = service.reserve(a["id"], city="Fortaleza")
    assert service.status()["global_used_micro"] == 10_000
    service.finish(a["id"], state="partial")
    service.claim()
    with pytest.raises(DomainError, match="global"):
        service.reserve(b["id"], city="Fortaleza")
    service.settle(hold["id"], cost_micro=1_750, treg_call_id="call-1")
    assert service.status()["global_used_micro"] == 1_750
    service.reserve(b["id"], city="Fortaleza", amount_micro=8_250)


def test_unknown_charge_stays_reserved(service):
    c = campaign(service)
    service.enqueue(c["id"])

    def timeout(**_kwargs):
        raise TregError("Resposta perdida")

    result = process_one(service, token="test-only", search=timeout)
    assert result["state"] == "failed"
    assert result["financial_state"] == "pending"
    assert service.status()["global_used_micro"] == 10_000


def test_ledger_reconciliation_releases_only_terminal_cost(service, monkeypatch):
    c = campaign(service)
    service.enqueue(c["id"])

    def timeout(**_kwargs):
        raise TregError("Resposta perdida", call_id="treg-call-1")

    run = process_one(service, token="test-only", search=timeout)
    monkeypatch.setattr("prospector.treg.get_call", lambda **_kwargs: {"ledger": [{"kind": "reserve"}], "charged_micro": 0})
    assert service.reconcile_pending(token="test-only")[0]["state"] == "pending"
    assert service.status()["global_used_micro"] == 10_000
    monkeypatch.setattr("prospector.treg.get_call", lambda **_kwargs: {"ledger": [{"kind": "reserve"}, {"kind": "settle"}], "charged_micro": 1750})
    assert service.reconcile_pending(token="test-only")[0]["state"] == "confirmed"
    assert service.status()["global_used_micro"] == 1750
    assert service.run(run["id"])["financial_state"] == "confirmed"


def test_recent_region_does_not_repeat_paid_search(service):
    c = campaign(service)
    service.enqueue(c["id"])
    invoked = []

    def fake_search(**kwargs):
        invoked.append(kwargs)
        return TregResult([place()], "call-1", 1_750)

    process_one(service, token="test-only", search=fake_search)
    service.enqueue(c["id"])
    result = process_one(service, token="test-only", search=fake_search)
    assert len(invoked) == 1
    assert result["state"] == "failed"
    assert "reconsulta" in result["error"]


def test_reject_unsafe_website(service):
    c = campaign(service)
    run = service.enqueue(c["id"])
    service.claim()
    item = {**place(), "website": "javascript:alert(1)"}
    service.add_place(run["id"], item, city="Fortaleza", uf="CE", niche=c["niche"])
    assert service.leads()["items"][0]["website"] is None
