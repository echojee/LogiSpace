from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException

from app.services.llm import gateway
from app.services.runtime_store import JsonStore
from logispace_domain.dossiers import all_dossiers, get_dossier
from logispace_domain.models import Citation, Conversation, ConversationAnswer, ConversationCreate, ConversationMemory, ConversationMessage, ConversationTurn

_store = JsonStore("conversations")


def create_conversation(request: ConversationCreate) -> Conversation:
    conversation = Conversation(
        conversation_id=f"conv_{uuid4().hex[:12]}",
        memory=ConversationMemory(active_work_ids=request.active_work_ids, spoiler_level=request.spoiler_level),
    )
    _store.save(conversation.conversation_id, conversation)
    return conversation


def get_conversation(conversation_id: str) -> Conversation:
    conversation = _store.load(conversation_id, Conversation)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def list_conversations() -> list[Conversation]:
    return sorted(_store.list(Conversation), key=lambda item: item.updated_at, reverse=True)


def _resolve_works(question: str, memory: ConversationMemory) -> list:
    mentioned = [dossier for dossier in all_dossiers() if dossier.work.canonical_title in question or any(alias and alias in question for alias in dossier.work.aliases)]
    if mentioned:
        return mentioned
    return [dossier for work_id in memory.active_work_ids if (dossier := get_dossier(work_id)) is not None]


def _context_for(dossiers: list) -> str:
    blocks = []
    for dossier in dossiers:
        entities = "\n".join(f"- [{item.entity_type}] {item.name}: {item.summary}" for item in dossier.entities)
        relations = "\n".join(f"- {item.source_id} --{item.relation}--> {item.target_id}: {item.note or ''}" for item in dossier.relations)
        blocks.append(f"Work: {dossier.work.canonical_title} ({dossier.work.work_id})\nEntities:\n{entities}\nRelations:\n{relations}")
    return "\n\n".join(blocks)


def _dossier_citations(dossiers: list) -> list[Citation]:
    return [Citation(citation_id=f"cite_{item.work.work_id}", label=f"?{item.work.canonical_title}?WorkDossier {item.dossier_version}", source_type="work_dossier", work_id=item.work.work_id, entity_ids=[entity.entity_id for entity in item.entities]) for item in dossiers]


def _fallback_answer(question: str, dossiers: list) -> tuple[str, str]:
    if not dossiers:
        return "The work is not available locally. Name a collected work or configure the model API for web search.", "insufficient"
    keywords = [part for part in question.replace("?", "").replace("?", "").replace("?", " ").split() if len(part) > 1]
    scored = []
    for dossier in dossiers:
        for item in dossier.entities:
            score = sum(part in item.name or part in item.summary for part in keywords)
            if item.name in question:
                score += 3
            elif len(item.name) >= 2 and item.name[:2] in question:
                score += 2
            if score:
                scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if scored:
        return "\n".join(f"- {item.name}?{item.summary}" for _, item in scored[:6]), "supported"
    title = dossiers[0].work.canonical_title
    return f"The WorkDossier for {title} lacks relevant evidence. Start deep research to fill this gap.", "insufficient"


def add_turn(conversation_id: str, request: ConversationTurn) -> ConversationAnswer:
    conversation = get_conversation(conversation_id)
    if request.spoiler_level is not None:
        conversation.memory.spoiler_level = request.spoiler_level
    conversation.messages.append(ConversationMessage(message_id=f"msg_{uuid4().hex[:12]}", role="user", content=request.content))
    dossiers = _resolve_works(request.content, conversation.memory)
    used_work_ids = [item.work.work_id for item in dossiers]
    if used_work_ids:
        conversation.memory.active_work_ids = used_work_ids
    conversation.memory.current_topic = request.content[:120]
    used_web = False
    citations = _dossier_citations(dossiers)
    status = "supported"
    if gateway.available:
        history = "\n".join(f"{item.role}: {item.content}" for item in conversation.messages[-8:])
        result = gateway.respond(
            instructions="You are the LogiSpace quick-answer agent. Prefer local evidence, search only when needed, never fabricate, respect spoiler settings, and answer in the user's language.",
            input_text=f"Spoiler level: {conversation.memory.spoiler_level.value}\nConversation:\n{history}\n\nLocal knowledge:\n{_context_for(dossiers) or 'None'}",
            web_search=request.allow_web_search and not dossiers,
        )
        answer_text = result.text
        used_web = result.used_web_search
        for index, annotation in enumerate(result.annotations):
            url = annotation.get("url")
            if url:
                citations.append(Citation(citation_id=f"web_{index}", label=annotation.get("title") or url, url=url, source_type="web"))
        if not answer_text:
            answer_text, status = _fallback_answer(request.content, dossiers)
        elif not dossiers:
            status = "partial"
    else:
        answer_text, status = _fallback_answer(request.content, dossiers)
    assistant = ConversationMessage(message_id=f"msg_{uuid4().hex[:12]}", role="assistant", content=answer_text, citations=citations)
    conversation.messages.append(assistant)
    conversation.title = conversation.messages[0].content[:32]
    conversation.memory.summary = "?".join(item.content[:80] for item in conversation.messages[-4:])
    conversation.updated_at = datetime.utcnow()
    _store.save(conversation.conversation_id, conversation)
    return ConversationAnswer(conversation_id=conversation.conversation_id, message=assistant, answer_status=status, used_work_ids=used_work_ids, used_web_search=used_web, suggest_deep_research=status in {"partial", "insufficient"} or used_web, memory=conversation.memory)


def clear_memory(conversation_id: str) -> Conversation:
    conversation = get_conversation(conversation_id)
    conversation.memory = ConversationMemory()
    conversation.updated_at = datetime.utcnow()
    _store.save(conversation_id, conversation)
    return conversation
