from pathlib import Path

from fastapi.testclient import TestClient

from prospector import auth
from prospector.service import ProspectorService
from prospector.web import create_app


def test_api_requires_login_and_csrf(tmp_path: Path):
    db_file = tmp_path / "app.db"
    db = ProspectorService(db_file)
    auth.set_admin(db.conn, "senha-longa-de-teste")
    db.close()
    app = create_app(db_file=db_file, start_worker=False)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/status").status_code == 401
        assert client.post("/api/login", json={"password": "errada"}).status_code == 401
        csrf = client.post("/api/login", json={"password": "senha-longa-de-teste"}).json()["csrf"]
        assert client.get("/api/status").status_code == 200
        body = {"name": "Teste", "niche": "dentista", "cities": [{"city": "Fortaleza", "uf": "CE"}]}
        assert client.post("/api/campaigns", json=body).status_code == 403
        assert client.post("/api/campaigns", json=body, headers={"X-CSRF-Token": csrf}).status_code == 200
        assert client.get("/api/settings/treg").json()["configured"] is False


def test_campaign_sources_can_be_added_and_removed_through_api(tmp_path: Path):
    db_file = tmp_path / "sources.db"
    db = ProspectorService(db_file)
    auth.set_admin(db.conn, "senha-longa-de-teste")
    db.close()
    with TestClient(create_app(db_file=db_file, start_worker=False), base_url="https://testserver") as client:
        csrf = client.post("/api/login", json={"password": "senha-longa-de-teste"}).json()["csrf"]
        headers = {"X-CSRF-Token": csrf}
        body = {"name": "Teste", "niche": "dentista", "cities": [{"city": "Fortaleza", "uf": "CE"}],
                "sources": ["google_maps", "instagram"]}
        campaign = client.post("/api/campaigns", json=body, headers=headers).json()
        assert campaign["sources"] == ["google_maps", "instagram"]
        url = "/api/campaigns/" + campaign["id"]
        assert client.patch(url, json={"sources": ["linkedin"]}, headers=headers).json()["sources"] == ["linkedin"]
        edited = client.patch(url, json={"name":"Clínica nova", "niche":"estética", "service":"Marketing",
            "cities":[{"city":"Teresina", "uf":"pi"}], "target_leads":40,
            "run_cap_micro":500_000, "monthly_cap_micro":2_000_000, "sources":["instagram", "linkedin"]},
            headers=headers).json()
        assert edited["name"] == "Clínica nova" and edited["service"] == "Marketing"
        assert edited["cities"] == [{"city":"Teresina", "uf":"PI"}]
        assert edited["target_leads"] == 40 and edited["run_cap_micro"] == 500_000
        assert edited["sources"] == ["instagram", "linkedin"]
        assert client.patch(url, json={"cities":[{"city":"Sem UF", "uf":"X"}]}, headers=headers).status_code == 400
        assert client.patch(url, json={"sources": []}, headers=headers).status_code == 400
        assert client.get("/api/campaigns").json()[0]["sources"] == ["instagram", "linkedin"]
