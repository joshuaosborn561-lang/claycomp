from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from claycomp.enrichers import ENRICHERS, get_enricher
from claycomp.records import load_csv_bytes, load_sample, records_from_dicts, records_to_csv_bytes, records_to_dicts
from claycomp.web.chat import stream_chat
from claycomp.web.schemas import ChatRequest, EnrichRequest, EnricherInfo, RecordDTO, dto_to_record, record_to_dto

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Claycomp", version="0.1.0")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)


@app.get("/api/health")
def health():
  return {"ok": True}


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
async def enrich_stream(req: EnrichRequest):
  enricher = get_enricher(req.enricher)
  records = [dto_to_record(r) for r in req.records]
  if req.row_ids:
    id_set = set(req.row_ids)
    targets = [r for r in records if r.id in id_set]
  else:
    targets = records

  async def generate() -> AsyncIterator[str]:
    total = len(targets)
    sem = asyncio.Semaphore(5)

    async def run_one(idx: int, rec: Record):
      async with sem:
        try:
          result = await enricher.enrich(rec)
          rec.set_enriched(enricher.output_column(), result.value)
          payload = {
            "type": "progress",
            "row_id": rec.id,
            "column": enricher.output_column(),
            "value": result.value,
            "done": idx + 1,
            "total": total,
          }
        except Exception as e:
          rec.set_enriched(enricher.output_column(), None)
          payload = {
            "type": "error",
            "row_id": rec.id,
            "column": enricher.output_column(),
            "error": str(e),
            "done": idx + 1,
            "total": total,
          }
        return payload

    tasks = [run_one(i, r) for i, r in enumerate(targets)]
    for coro in asyncio.as_completed(tasks):
      payload = await coro
      yield f"data: {json.dumps(payload)}\n\n"

    yield f"data: {json.dumps({'type': 'complete', 'records': [record_to_dto(r).model_dump() for r in records]})}\n\n"

  return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
  async def generate() -> AsyncIterator[str]:
    async for event in stream_chat(req.messages, req.records):
      yield event

  return StreamingResponse(generate(), media_type="text/event-stream")


if STATIC_DIR.is_dir():
  app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
