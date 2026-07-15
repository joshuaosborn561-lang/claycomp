from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from claycomp.models import Record


class RecordDTO(BaseModel):
    id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    title: str | None = None
    company: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    enriched: dict[str, Any] = Field(default_factory=dict)


class EnricherInfo(BaseModel):
    key: str
    name: str
    description: str
    requires_api_key: str | None = None


class ProviderInfoDTO(BaseModel):
    id: str
    name: str
    env_key: str
    models: list[str]
    default_model: str
    configured: bool


class EnrichRequest(BaseModel):
    records: list[RecordDTO]
    enricher: str
    row_ids: list[str] | None = None
    provider: str | None = None
    model: str | None = None
    custom_prompt: str | None = None
    column_name: str | None = None
    business_context: str | None = None
    email_providers: list[str] | None = None


class EnrichProgressEvent(BaseModel):
    type: str
    row_id: str | None = None
    column: str | None = None
    value: Any = None
    done: int = 0
    total: int = 0
    error: str | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    records: list[RecordDTO] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class SculptorRequest(BaseModel):
    messages: list[ChatMessage]
    records: list[RecordDTO] = Field(default_factory=list)
    columns: list[dict[str, Any]] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    business_context: str | None = None


class ColumnProposal(BaseModel):
    column_name: str
    label: str
    enricher_key: str
    custom_prompt: str | None = None
    reasoning: str | None = None


class TableMeta(BaseModel):
    id: str
    name: str
    row_count: int = 0
    updated_at: str | None = None
    created_at: str | None = None


class TableData(BaseModel):
    id: str | None = None
    name: str = "My Leads"
    records: list[RecordDTO] = Field(default_factory=list)
    columns: list[dict[str, Any]] = Field(default_factory=list)
    business_context: str | None = None
    email_providers: list[str] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ApiKeyStatus(BaseModel):
    set: bool
    masked: str | None = None


class ApiKeysStatusDTO(BaseModel):
    keys: dict[str, ApiKeyStatus]
    storage: str
    setup_required: bool = False
    setup_message: str | None = None


class ApiKeysUpdate(BaseModel):
    keys: dict[str, str] = Field(default_factory=dict)


def dto_to_record(dto: RecordDTO) -> Record:
    return Record.model_validate(dto.model_dump())


def record_to_dto(record: Record) -> RecordDTO:
    return RecordDTO.model_validate(record.model_dump())
