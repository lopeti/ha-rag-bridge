from __future__ import annotations

import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from arango import ArangoClient

from .. import schemas

router = APIRouter()


def _doc_exists(db, doc_id: str) -> bool:
    if '/' not in doc_id:
        return False
    col_name, _ = doc_id.split('/', 1)
    return db.collection(col_name).has(doc_id)


@router.post('/graph/edge', response_model=schemas.EdgeResult)
async def add_edge(edge: schemas.EdgeCreate, request: Request) -> schemas.EdgeResult:
    arango = ArangoClient(hosts=os.environ['ARANGO_URL'])
    db_name = os.getenv('ARANGO_DB', '_system')
    db = arango.db(db_name, username=os.environ['ARANGO_USER'], password=os.environ['ARANGO_PASS'])
    if not _doc_exists(db, edge._from):
        raise HTTPException(status_code=422, detail='_from not found')
    if not _doc_exists(db, edge._to):
        raise HTTPException(status_code=422, detail='_to not found')

    edge_key = f"{edge._from.replace('/', '_')}-{edge._to.replace('/', '_')}-{edge.label}"
    edge_doc = {
        '_key': edge_key,
        '_from': edge._from,
        '_to': edge._to,
        'label': edge.label,
        'weight': edge.weight,
        'source': edge.source or request.headers.get('X-Caller', 'api'),
        'ts_created': edge.ts_created or datetime.utcnow().isoformat(),
    }
    edge_coll = db.collection('edge')
    result = edge_coll.insert(edge_doc, overwrite=True, overwrite_mode='update')
    action = 'updated' if '_old_rev' in result else 'inserted'
    return {'status': 'ok', 'edge_key': edge_key, 'action': action}

