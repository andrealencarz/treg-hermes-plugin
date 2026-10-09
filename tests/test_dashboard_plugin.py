import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from prospector import schedule
from prospector.secrets import save_token, token_hint
from prospector.service import ProspectorService


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_manifest_and_embedded_api(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    manifest = json.loads((ROOT / "dashboard/manifest.json").read_text())
    assert manifest["name"] == "hermes-prospector"
    assert manifest["tab"]["path"] == "/prospector"
    assert (ROOT / "dashboard" / manifest["entry"]).is_file()
    assert (ROOT / "dashboard" / manifest["css"]).is_file()
    assert (ROOT / "dashboard" / manifest["api"]).is_file()

    spec = importlib.util.spec_from_file_location("test_hermes_prospector_dashboard", ROOT / "dashboard/plugin_api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    host = FastAPI()
    host.include_router(module.router, prefix="/api/plugins/hermes-prospector")
    with TestClient(host, base_url="https://testserver") as client:
        base = "/api/plugins/hermes-prospector"
        assert client.get(base + "/health").json()["mode"] == "hermes-dashboard"
        initial = client.get(base + "/status").json()
        assert initial["treg_configured"] is False
        assert initial["treg_token_hint"] is None
        secret = "test-token-ABCDE"
        save_token(secret)
        status = client.get(base + "/status")
        assert status.json()["treg_token_hint"] == "••••••••BCDE"
        assert secret not in status.text
        settings = client.get(base + "/settings/treg")
        assert settings.json()["token_hint"] == "••••••••BCDE"
        assert secret not in settings.text
        save_token("other-token-WXYZ")
        assert client.get(base + "/status").json()["treg_token_hint"] == "••••••••WXYZ"
        created = client.post(base + "/campaigns", json={
            "name": "Exemplo", "niche": "dentista", "cities": [{"city": "Fortaleza", "uf": "CE"}],
        })
        assert created.status_code == 200, created.text
        assert client.get(base + "/campaigns").json()[0]["name"] == "Exemplo"
        assert client.patch(base + "/campaigns/nao-existe/state", json={"state": "paused"}).status_code == 400
        assert client.post(base + "/leads/nao-existe/analyze-site").status_code == 400


def test_short_token_hint_never_reveals_token():
    assert token_hint("short") == "••••••••"


def test_ui_install_schedule_script_uses_hermes_python(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("PROSPECTOR_BIN", raising=False)
    path = schedule._write_script("campaign-test")
    content = path.read_text()
    assert "PYTHONPATH=" in content
    assert "-m prospector.cli" in content
    assert "schedule-tick campaign-test" in content
    assert "worker-once" in content
    assert path.stat().st_mode & 0o777 == 0o700


def test_sqlite_request_connection_can_be_used_and_closed_in_other_threads(tmp_path):
    service = ProspectorService(tmp_path / "cross-thread.db")
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(lambda: service.conn.execute("SELECT 1").fetchone()[0]).result() == 1
        pool.submit(service.close).result()
