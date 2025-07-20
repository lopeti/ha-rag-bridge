import os
import json
import zipfile
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
import app.routers.admin as admin

client = TestClient(app)


def setup_env():
    os.environ['ADMIN_TOKEN'] = 'tok'
    os.environ['ARANGO_URL'] = 'http://db'
    os.environ['ARANGO_USER'] = 'root'
    os.environ['ARANGO_PASS'] = 'pass'


def test_export(monkeypatch, tmp_path):
    setup_env()
    mock_col = MagicMock()
    mock_col.all.return_value = [{"_key": "1", "val": 1}]
    mock_db = MagicMock()
    mock_db.collections.return_value = [{"name": "entity"}]
    mock_db.collection.return_value = mock_col
    mock_arango = MagicMock()
    mock_arango.db.return_value = mock_db
    monkeypatch.setattr(admin, 'ArangoClient', MagicMock(return_value=mock_arango))

    resp = client.get('/admin/export', headers={'X-Admin-Token': 'tok', 'Accept': 'application/zip'})
    assert resp.status_code == 200
    zip_path = tmp_path / 'out.zip'
    zip_path.write_bytes(resp.content)
    with zipfile.ZipFile(zip_path) as zf:
        assert 'entity.jsonl' in zf.namelist()
        data = zf.read('entity.jsonl').decode().splitlines()
        assert json.loads(data[0]) == {"_key": "1", "val": 1}
