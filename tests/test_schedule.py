import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from prospector.db import now
from prospector.schedule import next_occurrences, tick, validate
from prospector.service import ProspectorService


def test_daily_tick_is_idempotent(tmp_path: Path):
    service = ProspectorService(tmp_path / "test.db")
    campaign = service.create_campaign(name="Teste", niche="dentista", cities=[{"city": "Recife", "uf": "PE"}])
    service.set_campaign_state(campaign["id"], "active")
    zone = ZoneInfo("America/Fortaleza")
    reference = datetime(2026, 10, 9, 9, 0, tzinfo=zone)
    service.conn.execute("""INSERT INTO schedule_binding(campaign_id,frequency,days_json,times_json,timezone,state,updated_at)
        VALUES(?,'daily','[]',?,'America/Fortaleza','active',?)""",
        (campaign["id"], json.dumps(["09:00"]), now()))
    first = tick(service, campaign["id"], reference)
    second = tick(service, campaign["id"], reference)
    assert first["queued"] is True
    assert second["queued"] is False
    assert len(service.runs()) == 1
    service.close()


def test_preview_uses_campaign_timezone():
    spec = validate("weekdays", [0, 4], ["09:00", "15:00"], "America/Fortaleza")
    reference = datetime(2026, 10, 9, 8, 0, tzinfo=ZoneInfo("America/Fortaleza"))
    next_three = next_occurrences(spec, reference=reference)
    assert [x[11:16] for x in next_three] == ["09:00", "15:00", "09:00"]
