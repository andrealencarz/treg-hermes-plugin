import csv
import json
from pathlib import Path

from prospector.legacy import import_file, preview
from prospector.service import ProspectorService


def test_import_preview_backup_and_repeat(tmp_path: Path):
    source = tmp_path / "old.csv"
    rows = [
        {"id": "old-1", "nome": "Clínica A", "cidade": "Fortaleza", "uf": "CE",
         "telefone": "+55 85 3000-0000", "status": "Contatado", "observacoes": "Retornar",
         "custo_usd": "0,0125"},
        {"id": "old-2", "nome": "Clínica B", "cidade": "Fortaleza", "uf": "CE",
         "telefone": "+55 85 3000-0000", "status": "Novo", "observacoes": ""},
    ]
    with source.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    original = source.read_bytes()
    service = ProspectorService(tmp_path / "data" / "prospector.db")
    try:
        assert preview(source)["records"] == 2
        result = import_file(service, source)
        assert result["records_imported"] == 2
        assert Path(result["backup"]).parent == tmp_path / "data" / "backups"
        assert Path(result["backup"]).is_file()
        assert source.read_bytes() == original
        assert service.leads()["total"] == 2
        assert import_file(service, source)["records_imported"] == 0
        recorded = service.conn.execute("SELECT raw_json,cost_micro FROM legacy_record WHERE row_index=0").fetchone()
        assert json.loads(recorded["raw_json"])["observacoes"] == "Retornar"
        assert recorded["cost_micro"] == 12_500
        assert service.conn.execute("SELECT COUNT(*) FROM lead").fetchone()[0] == 2
    finally:
        service.close()
