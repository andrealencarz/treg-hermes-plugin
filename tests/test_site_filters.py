import json

import pytest
from fastapi.testclient import TestClient

from prospector import auth
from prospector.service import DomainError, ProspectorService
from prospector.web import create_app


def test_site_quality_filters_and_csv(tmp_path):
    path = tmp_path / "filters.db"
    db = ProspectorService(path)
    auth.set_admin(db.conn, "senha-longa-de-teste")
    for lead_id, website in [
        ("none", None), ("pending", "https://pending.example"),
        ("offline", "https://offline.example"), ("links", "https://linktr.ee/exemplo"),
        ("weak", "https://weak.example"), ("good", "https://good.example"),
        ("unclear", "https://unclear.example"),
    ]:
        db.conn.execute("""INSERT INTO lead(id,name,website,first_seen_at,last_seen_at)
            VALUES(?,?,?,?,?)""", (lead_id, lead_id, website, "2026-10-09", "2026-10-09"))
    for lead_id, availability, page_type, score in [
        ("offline", "offline", "website", None), ("links", "online", "links", None),
        ("weak", "online", "website", 45), ("good", "online", "website", 85),
        ("unclear", "online", "website", None),
    ]:
        website = db.conn.execute("SELECT website FROM lead WHERE id=?", (lead_id,)).fetchone()[0]
        db.conn.execute("""INSERT INTO lead_site_audit
            (lead_id,website,checked_at,availability,page_type,issues_json,seo_score)
            VALUES(?,?,?,?,?,?,?)""", (lead_id, website, "2026-10-09", availability, page_type, json.dumps([]), score))

    ids = lambda quality: {lead["id"] for lead in db.leads(site_quality=quality)["items"]}
    assert ids("no_site") == {"none"}
    assert ids("poor") == {"offline", "links", "weak"}
    assert ids("good") == {"good"}
    assert ids("unanalyzed") == {"pending", "unclear"}
    with pytest.raises(DomainError, match="Filtro de site inválido"):
        db.leads(site_quality="qualquer")
    db.conn.execute("UPDATE lead SET website='https://changed.example' WHERE id='good'")
    assert "good" not in ids("good") and "good" in ids("unanalyzed")
    db.close()

    with TestClient(create_app(db_file=path, start_worker=False), base_url="https://testserver") as client:
        client.post("/api/login", json={"password": "senha-longa-de-teste"})
        assert client.get("/api/leads?site_quality=no_site").json()["total"] == 1
        result = client.get("/api/leads?site_quality=poor").json()
        assert result["total"] == 3
        csv_text = client.get("/api/leads/export.csv?site_quality=poor").text
        assert "offline" in csv_text and "links" in csv_text and "weak" in csv_text
        assert "pending" not in csv_text and "good" not in csv_text
