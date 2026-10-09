import socket

import pytest
from fastapi.testclient import TestClient

from prospector import auth, site_audit
from prospector.service import ProspectorService
from prospector.web import create_app


HTML = '''<html lang="pt-BR"><head><title>Clínica Exemplo</title>
<meta name="description" content="Clínica de estética em Teresina">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="canonical" href="https://clinica.example/"></head>
<body><h1>Clínica Exemplo</h1></body></html>'''


def test_site_analysis_classifies_provider_and_basic_seo():
    page = site_audit.analyze("https://clinica.example", lambda _: (200, "https://clinica.example/", "text/html", HTML))
    assert page["availability"] == "online"
    assert page["page_type"] == "website" and page["seo_score"] == 100
    weak = site_audit.analyze("https://clinica.example", lambda _: (200, "https://clinica.example/", "text/html",
        '<html><head><meta name="robots" content="noindex"></head><body>Olá</body></html>'))
    assert weak["seo_score"] < 60
    assert "Página marcada como noindex" in weak["issues"]
    third_party = site_audit.analyze("https://linktr.ee/clinica", lambda _: (200, "https://www.ifood.com.br/loja/1", "text/html", HTML))
    assert third_party["page_type"] == "delivery" and third_party["provider"] == "iFood"
    assert third_party["seo_score"] is None
    shopmy = site_audit.analyze("https://shopmy.us/shop/clinica", lambda _: (200, "https://shopmy.us/shop/clinica", "text/html", HTML))
    assert shopmy["page_type"] == "links" and shopmy["provider"] == "ShopMy"
    blocked = site_audit.analyze("https://clinica.example", lambda _: (403, "https://clinica.example", "text/html", ""))
    assert blocked["availability"] == "blocked"
    offline = site_audit.analyze("https://clinica.example", lambda _: (_ for _ in ()).throw(TimeoutError()))
    assert offline["availability"] == "offline"
    assert offline["issues"] == ["Tempo limite ao acessar o site"]
    links = "<html><body><h1>Links</h1>" + "".join(
        f'<a href="https://site{i}.example/">Link {i}</a>' for i in range(5)) + "</body></html>"
    possible = site_audit.analyze("https://negocio.example", lambda _: (200, "https://negocio.example/", "text/html", links))
    assert possible["page_type"] == "possible_links" and possible["seo_score"] is None


def test_site_analysis_rejects_private_targets(monkeypatch):
    with pytest.raises(site_audit.UnsafeSite):
        site_audit._safe_target("http://127.0.0.1/")
    with pytest.raises(site_audit.UnsafeSite):
        site_audit._safe_target("http://metadata.google.internal/")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, 1, 6, "", ("10.0.0.2", 443))])
    with pytest.raises(site_audit.UnsafeSite):
        site_audit._safe_target("https://example.org/")


def test_audit_persists_and_api_requires_authentication(tmp_path, monkeypatch):
    path = tmp_path / "audit.db"
    db = ProspectorService(path)
    auth.set_admin(db.conn, "senha-longa-de-teste")
    db.conn.execute("""INSERT INTO lead(id,name,website,first_seen_at,last_seen_at)
        VALUES('lead-1','Clínica','https://clinica.example','2026-10-09','2026-10-09')""")
    db.close()
    monkeypatch.setattr("prospector.service.analyze_website", lambda _: site_audit.analyze(
        "https://clinica.example", lambda _url: (200, "https://clinica.example/", "text/html", HTML)))
    with TestClient(create_app(db_file=path, start_worker=False), base_url="https://testserver") as client:
        url = "/api/leads/lead-1/analyze-site"
        assert client.post(url).status_code == 401
        csrf = client.post("/api/login", json={"password":"senha-longa-de-teste"}).json()["csrf"]
        assert client.post(url).status_code == 403
        result = client.post(url, headers={"X-CSRF-Token":csrf})
        assert result.status_code == 200 and result.json()["seo_score"] == 100
        assert client.get("/api/leads").json()["items"][0]["site_audit"]["page_type"] == "website"
        assert client.get("/api/leads/lead-1").json()["site_audit"]["checked_at"]
        assert "SEO (0-100)" in client.get("/api/leads/export.csv").text
    db = ProspectorService(path)
    db.conn.execute("UPDATE lead SET website='https://outro.example' WHERE id='lead-1'")
    assert db.lead("lead-1")["site_audit"] is None
    db.close()
