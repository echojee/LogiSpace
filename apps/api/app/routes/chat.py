from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.services.search import query_dossiers

router = APIRouter()


class ChatQuery(BaseModel):
    question: str = Field(min_length=1)
    source_work_ids: list[str] = Field(default_factory=list)


class ChatAnswer(BaseModel):
    intent: str
    answer: str
    source_work_ids: list[str]
    matched_entity_ids: list[str]
    links: list[dict[str, str]]


@router.post("/query", response_model=ChatAnswer)
def query(request: ChatQuery) -> ChatAnswer:
    result = query_dossiers(request.question, request.source_work_ids)
    return ChatAnswer(**result.__dict__)