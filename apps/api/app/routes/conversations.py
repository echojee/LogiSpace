from fastapi import APIRouter

from app.services.conversations import add_turn, clear_memory, create_conversation, get_conversation, list_conversations
from logispace_domain.models import Conversation, ConversationAnswer, ConversationCreate, ConversationTurn

router = APIRouter()


@router.post("", response_model=Conversation)
def create(request: ConversationCreate) -> Conversation:
    return create_conversation(request)


@router.get("", response_model=list[Conversation])
def list_items() -> list[Conversation]:
    return list_conversations()


@router.get("/{conversation_id}", response_model=Conversation)
def get_item(conversation_id: str) -> Conversation:
    return get_conversation(conversation_id)


@router.post("/{conversation_id}/messages", response_model=ConversationAnswer)
def message(conversation_id: str, request: ConversationTurn) -> ConversationAnswer:
    return add_turn(conversation_id, request)


@router.delete("/{conversation_id}/memory", response_model=Conversation)
def delete_memory(conversation_id: str) -> Conversation:
    return clear_memory(conversation_id)
