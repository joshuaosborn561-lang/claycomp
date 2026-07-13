from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from claycomp.enrichers import ENRICHERS, get_enricher
from claycomp.llm import list_providers
from claycomp.models import Record
from claycomp.records import load_csv_bytes, load_sample, records_from_dicts, records_to_csv_bytes, records_to_dicts
from claycomp.web.chat import stream_chat
from claycomp.web.schemas import (
    ApiKeysStatusDTO,
    ApiKeysUpdate,
    ChatRequest,
    EnrichRequest,
    EnricherInfo,
    ProviderInfoDTO,
    SculptorRequest,
    TableData,
    dto_to_record,
    record_to_dto,
)
from claycomp.storage.api_keys import (
    API_KEY_NAMES,
    StorageNotConfiguredError,
    get_api_key_store,
    mask_api_key,
)
from claycomp.storage.config import STORAGE_SETUP_MESSAGE, storage_backend
from claycomp.storage.supabase_client import SupabaseError
from claycomp.web.sculptor import stream_sculptor
from claycomp.keys import bind_api_keys
from claycomp.web.middleware import ApiKeysMiddleware

from claycomp.storage.tables import get_table_store

# Local dev: serve built frontend from frontend/dist
STATIC_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"

app = FastAPI(title="Claycomp", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiKeysMiddleware)


@app.get("/api/health")
def health():
    return {"ok": True, "storage": storage_backend()}


@app.get("/api/settings/keys", response_model=ApiKeysStatusDTO)
async def get_api_keys_status():
    store = get_api_key_store()
    keys = await store.get_keys()
    backend = storage_backend()
    return ApiKeysStatusDTO(
        keys={
            name: {
                "set": bool(keys.get(name)),
                "masked": mask_api_key(keys[name]) if keys.get(name) else None,
            }
            for name in API_KEY_NAMES
        },
        storage=backend,
        setup_required=backend == "unconfigured",
        setup_message=STORAGE_SETUP_MESSAGE if backend == "unconfigured" else None,
    )


@app.put("/api/settings/keys", response_model=ApiKeysStatusDTO)
async def save_api_keys(body: ApiKeysUpdate):
    store = get_api_key_store()
    try:
        saved = await store.save_keys(body.keys)
    except (StorageNotConfiguredError, SupabaseError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    backend = storage_backend()
    return ApiKeysStatusDTO(
        keys={
            name: {
                "set": bool(saved.get(name)),
                "masked": mask_api_key(saved[name]) if saved.get(name) else None,
            }
            for name in API_KEY_NAMES
        },
        storage=backend,
        setup_required=backend == "unconfigured",
        setup_message=STORAGE_SETUP_MESSAGE if backend == "unconfigured" else None,
    )


@app.get("/api/tables")
async def list_tables():
    try:
        store = get_table_store()
        return {"tables": await store.list_tables()}
    except SupabaseError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/tables/{table_id}")
async def get_table(table_id: str):
    try:
        store = get_table_store()
        table = await store.get_table(table_id)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        return table
    except SupabaseError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/api/tables")
async def create_table(body: TableData):
    try:
        store = get_table_store()
        return await store.save_table(body.model_dump())
    except SupabaseError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.put("/api/tables/{table_id}")
async def update_table(table_id: str, body: TableData):
    try:
        store = get_table_store()
        data = body.model_dump()
        data["id"] = table_id
        return await store.save_table(data)
    except SupabaseError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.delete("/api/tables/{table_id}")
async def delete_table(table_id: str):
    try:
        store = get_table_store()
        await store.delete_table(table_id)
        return {"ok": True}
    except SupabaseError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/providers", response_model=list[ProviderInfoDTO])
def providers():
    return [ProviderInfoDTO(**p.__dict__) for p in list_providers()]


@app.get("/api/enrichers", response_model=list[EnricherInfo])
def list_enrichers():
    result = []
    for key, cls in ENRICHERS.items():
        e = cls()
        result.append(EnricherInfo(
            key=key,
            name=e.name,
            description=e.description,
            requires_api_key=e.requires_api_key,
        ))
    return result


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    data = await file.read()
    records = load_csv_bytes(data)
    return {"records": records_to_dicts(records), "count": len(records)}


@app.get("/api/sample")
def sample_data():
    records = load_sample()
    return {"records": records_to_dicts(records), "count": len(records)}


@app.post("/api/export")
def export_csv(body: dict):
    records = records_from_dicts(body.get("records", []))
    content = records_to_csv_bytes(records)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=enriched.csv"},
    )


@app.post("/api/enrich/stream")
async def enrich_stream(req: EnrichRequest, request: Request):
    enricher = get_enricher(
        req.enricher,
        provider=req.provider,
        model=req.model,
        custom_prompt=req.custom_prompt,
        column_name=req.column_name,
    )
    records = [dto_to_record(r) for r in req.records]
    if req.row_ids:
        id_set = set(req.row_ids)
        targets = [r for r in records if r.id in id_set]
    else:
        targets = records

    keys_header = request.headers.get("x-claycomp-keys", "")

    async def generate() -> AsyncIterator[str]:
        await bind_api_keys(keys_header)
        total = len(targets)
        sem = asyncio.Semaphore(5)

        async def run_one(idx: int, rec: Record):
            async with sem:
                try:
                    result = await enricher.enrich(rec)
                    rec.set_enriched(enricher.output_column(), result.value)
                    return {
                        "type": "progress",
                        "row_id": rec.id,
                        "column": enricher.output_column(),
                        "value": result.value,
                        "done": idx + 1,
                        "total": total,
                    }
                except Exception as e:
                    rec.set_enriched(enricher.output_column(), None)
                    return {
                        "type": "error",
                        "row_id": rec.id,
                        "column": enricher.output_column(),
                        "error": str(e),
                        "done": idx + 1,
                        "total": total,
                    }

        tasks = [run_one(i, r) for i, r in enumerate(targets)]
        for coro in asyncio.as_completed(tasks):
            payload = await coro
            yield f"data: {json.dumps(payload)}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'records': [record_to_dto(r).model_dump() for r in records]})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    keys_header = request.headers.get("x-claycomp-keys", "")

    async def generate() -> AsyncIterator[str]:
        await bind_api_keys(keys_header)
        async for event in stream_chat(req.messages, req.records, provider=req.provider, model=req.model):
            yield event

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/sculptor/stream")
async def sculptor_stream(req: SculptorRequest, request: Request):
    keys_header = request.headers.get("x-claycomp-keys", "")

    async def generate() -> AsyncIterator[str]:
        await bind_api_keys(keys_header)
        async for event in stream_sculptor(
            req.messages,
            req.records,
            req.columns,
            provider=req.provider,
            model=req.model,
            business_context=req.business_context,
        ):
            yield event

    return StreamingResponse(generate(), media_type="text/event-stream")


# Serve SPA locally only — on Vercel, static files come from frontend/dist via CDN
if not os.getenv("VERCEL") and STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
