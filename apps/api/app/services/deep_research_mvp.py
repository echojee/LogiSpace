from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import BackgroundTasks, HTTPException

from app.services import orchestrator_v4
from app.services import knowledge_memory_v4
from app.services import report_knowledge_v4
from app.services import research_repository_v4 as repository
from app.services.working_memory_v4 import record as record_checkpoint
from logispace_domain.models_v4 import ResearchJobCreateV4
from logispace_domain.models_v4_runtime import (
    ResearchReportCitationV4,
    ResearchReportV4,
    ResearchRuntimeV4,
)

_ACTIVE_POLLS: set[str] = set()
_POLL_LOCK = Lock()
_ACTIVE_RUNS: set[str] = set()
_RUN_LOCK = Lock()
_SNAPSHOT_LOCK = Lock()

SYSTEM_PROMPT = """你是 LogiSpace 的作品深度研究员。你的任务是针对用户指定的作品及媒体版本，使用网络搜索进行充分、严谨的研究，并用中文写成一篇可以独立阅读的深度研究报告。

研究规则：
1. 必须先辨认作品及指定媒体类型，避免混入同名作品或其他改编版本；如引用改编版本，只能明确标注为比较材料。
2. 必须主动搜索并综合多个可靠来源；优先使用作者/出版方/制作方等官方资料、原始访谈、学术或专业研究、可信参考资料。
3. 事实陈述必须附可点击的来源引用。来源不一致时，明确写出分歧，不要自行编造结论。
4. 报告允许完整剧透。要区分作品明确呈现的事实、来源支持的解释，以及你根据材料作出的分析。
5. 不要输出研究计划、JSON、知识图谱或待办事项，只输出最终 Markdown 研究报告。

当相应条目被用户勾选时，报告应覆盖以下基础板块：
- 人物与人物关系：主要人物身份、秘密、动机、关系变化，以及这些关系如何推动情节。
- 多重时间线：至少区分故事真实发生顺序与作品向受众披露信息的叙事顺序；适用时补充调查/重建时间线。
- 核心诡计：诡计成立所依赖的前提、误导方式、被隐藏的假设、伏笔、揭示过程及其公平性。
- 死亡与作案手法：逐项说明受害者、表面现象、实际手法、执行条件、时间位置及相关证据；若作品不涉及杀人，应说明不适用并分析相应的核心冲突机制。

建议结构：标题、研究范围与版本说明、执行摘要、作品背景与核心命题、用户选中的计划板块、综合分析、仍有争议或证据不足之处、参考来源。避免只做剧情复述，重点解释作品为何这样运作。"""


def _model_name() -> str:
    return os.getenv("LOGISPACE_DEEP_RESEARCH_MODEL", os.getenv("LOGISPACE_RESEARCH_MODEL", "gpt-5.6-sol"))


def build_research_prompt(job: ResearchRuntimeV4) -> str:
    media_type = getattr(job.work.media_type, "value", job.work.media_type)
    creators = "、".join(job.work.creators) if job.work.creators else "未提供"
    planning = job.storm_planning
    selected_ids = set(job.plan.selected_unit_ids if job.plan else [])
    selected_units = [
        unit for unit in (job.plan.units if job.plan else [])
        if not selected_ids or unit.unit_id in selected_ids
    ]
    outline = "\n\n".join(
        f"## {index}. {unit.question}\n"
        f"研究意义：{unit.why_it_matters}\n"
        f"应覆盖：{'、'.join(unit.required_outputs)}\n"
        f"完成标准：{'；'.join(unit.done_when)}"
        for index, unit in enumerate(selected_units, 1)
    ) or (planning.research_outline.markdown if planning else "尚无结构化大纲")
    perspectives = "\n".join(
        f"- {item.title}：{item.description}" for item in (planning.perspectives if planning else [])
    ) or "- 采用用户批准的研究方向"
    dialogue = "\n".join(
        f"- [{turn.perspective_id}] {turn.question}；研究意图：{turn.research_intent}；未决：{'、'.join(turn.unresolved_questions) or '无'}"
        for turn in (planning.research_turns if planning else [])
    ) or "- 无"
    return f"""请严格依据已获人工批准的 Plan Prompt，对以下作品进行深度研究并产出最终报告：

作品名称：{job.work.canonical_title}
媒体类型：{media_type}
指定版本：{job.brief.media_version}
创作者：{creators}
用户特别想弄清的内容：{job.brief.user_goal}
目标读者：{job.brief.audience}

研究视角：
{perspectives}

规划阶段对话摘要（全部只是研究线索或待验证假设，不得当作事实引用）：
{dialogue}

已批准的研究增强大纲：
{outline}

只执行上方已批准的大纲条目；未被勾选的计划不得自行加入报告。按大纲主动搜索、交叉验证并输出带引用 Markdown；明确保留证据不足与来源冲突。"""


def build_request_payload(job: ResearchRuntimeV4) -> dict:
    return {
        "model": _model_name(),
        "instructions": SYSTEM_PROMPT,
        "input": build_research_prompt(job),
        "tools": [{"type": "web_search"}],
        "max_tool_calls": int(os.getenv("LOGISPACE_DEEP_RESEARCH_MAX_TOOL_CALLS", "6")),
        "background": True,
    }


def _extract_report(data: dict, prompt: str, title: str) -> ResearchReportV4:
    text_parts: list[str] = []
    citations: list[ResearchReportCitationV4] = []
    seen_urls: set[str] = set()
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") != "output_text":
                continue
            text_parts.append(content.get("text", ""))
            for annotation in content.get("annotations", []):
                citation = annotation.get("url_citation", annotation)
                url = citation.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                citations.append(ResearchReportCitationV4(
                    title=citation.get("title", ""), url=url,
                    start_index=citation.get("start_index"), end_index=citation.get("end_index"),
                ))
    markdown = "\n\n".join(part.strip() for part in text_parts if part.strip())
    if not markdown:
        raise RuntimeError("OpenAI Deep Research completed without a report")
    incomplete_reason = (data.get("incomplete_details") or {}).get("reason")
    return ResearchReportV4(
        title=f"《{title}》深度研究报告", markdown=markdown, citations=citations,
        prompt=prompt, model=str(data.get("model", _model_name())),
        provider_response_id=data.get("id"), usage=data.get("usage", {}),
        incomplete_reason=incomplete_reason,
    )


def _response_snapshot_path(job_id: str) -> Path:
    return repository.ROOT / "_responses" / f"{job_id}.json"


def _save_response_snapshot(job_id: str, data: dict) -> None:
    # Polling and request-creation threads may observe the same response at
    # nearly the same time. Serialize the atomic replace on Windows, where two
    # writers sharing one .tmp file otherwise raise WinError 32.
    with _SNAPSHOT_LOCK:
        target = _response_snapshot_path(job_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        # Validate before the atomic replace so a partial response can never become canonical.
        json.loads(temporary.read_text(encoding="utf-8"))
        temporary.replace(target)


def _complete_from_response(job: ResearchRuntimeV4, data: dict) -> ResearchRuntimeV4:
    prompt = build_research_prompt(job)
    job.research_report = _extract_report(data, prompt, job.work.canonical_title)
    job.report_memory_status = "pending_approval"
    job.status = "partially_completed" if job.research_report.incomplete_reason else "completed"
    job.provider_response_id = data.get("id") or job.provider_response_id
    if job.plan is not None:
        job.plan.approved = True
    if job.research_report.incomplete_reason:
        note = f"Report preserved from incomplete OpenAI output: {job.research_report.incomplete_reason}"
        if note not in job.errors:
            job.errors.append(note)
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="search_and_draft", status="completed")
    return job


def review_report_memory(job_id: str, decision: str) -> ResearchRuntimeV4:
    job = orchestrator_v4.get(job_id)
    if job.research_report is None:
        raise HTTPException(409, "Research report is not ready for memory review")
    if decision not in {"approve", "reject"}:
        raise HTTPException(422, "decision must be approve or reject")
    if decision == "reject":
        job.report_memory_status = "rejected"
        job.updated_at = datetime.now(timezone.utc)
        repository.save(job)
        return job
    existing_version = knowledge_memory_v4.version_for_source_job(job.work.work_id, job.job_id)
    if job.report_memory_status == "deposited" and existing_version:
        if job.published_version != existing_version:
            job.published_version = existing_version
            job.updated_at = datetime.now(timezone.utc)
            repository.save(job)
        return job
    record_checkpoint(job, stage="deposit", status="started")
    try:
        knowledge_memory_v4.deposit_report(job)
        record_checkpoint(job, stage="projection", status="started")
        verified, case_file = report_knowledge_v4.build(job)
        version = knowledge_memory_v4.publish_report_knowledge(job, verified, case_file)
    except (OSError, RuntimeError, ValueError) as error:
        job.errors.append(f"Knowledge report deposit failed: {error}")
        repository.save(job)
        record_checkpoint(job, stage="deposit", status="failed", error=str(error))
        record_checkpoint(job, stage="projection", status="failed", error=str(error))
        raise HTTPException(500, f"Report was preserved, but reusable knowledge publication failed: {error}") from error
    job.verified_knowledge = verified
    job.case_file = case_file
    job.published_version = version
    job.report_memory_status = "deposited"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="projection", status="completed")
    record_checkpoint(job, stage="deposit", status="completed")
    return job


def rebuild_report_memory(job_id: str) -> ResearchRuntimeV4:
    """Create a new immutable knowledge version when a prior projection was incomplete."""
    job = orchestrator_v4.get(job_id)
    if job.research_report is None or job.report_memory_status != "deposited":
        raise HTTPException(409, "Only a deposited research report can rebuild reusable knowledge")
    record_checkpoint(job, stage="projection", status="started", attempt=2)
    try:
        verified, case_file = report_knowledge_v4.build(job)
        version = knowledge_memory_v4.publish_report_knowledge(job, verified, case_file, force_new=True)
    except (OSError, RuntimeError, ValueError) as error:
        job.errors.append(f"Knowledge rebuild failed: {error}")
        repository.save(job)
        record_checkpoint(job, stage="projection", status="failed", attempt=2, error=str(error))
        raise HTTPException(500, f"Reusable knowledge rebuild failed: {error}") from error
    job.verified_knowledge = verified
    job.case_file = case_file
    job.published_version = version
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="projection", status="completed", attempt=2)
    return job


def _response_request(url: str, *, api_key: str, payload: dict | None = None, timeout: int = 60) -> dict:
    request = Request(
        url,
        data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _poll_existing(job_id: str) -> ResearchRuntimeV4:
    job = orchestrator_v4.get(job_id)
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or not job.provider_response_id:
        return _fail(job, RuntimeError("Cannot resume research without OPENAI_API_KEY and provider_response_id"))
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    deadline = time.monotonic() + int(os.getenv("LOGISPACE_DEEP_RESEARCH_POLL_WINDOW_SECONDS", "3600"))
    while time.monotonic() < deadline:
        try:
            data = _response_request(
                f"{base_url}/responses/{job.provider_response_id}", api_key=api_key,
                timeout=int(os.getenv("LOGISPACE_DEEP_RESEARCH_STATUS_TIMEOUT_SECONDS", "60")),
            )
            _save_response_snapshot(job_id, data)
            status = data.get("status")
            if status in {"completed", "incomplete"}:
                return _complete_from_response(orchestrator_v4.get(job_id), data)
            if status in {"failed", "cancelled"}:
                return _fail(orchestrator_v4.get(job_id), RuntimeError(
                    f"OpenAI background response {status}: {data.get('error') or data.get('incomplete_details')}"
                ))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            job = orchestrator_v4.get(job_id)
            message = f"Transient OpenAI status read: {error}"
            if message not in job.errors:
                job.errors.append(message)
                repository.save(job)
        time.sleep(int(os.getenv("LOGISPACE_DEEP_RESEARCH_POLL_INTERVAL_SECONDS", "5")))
    return orchestrator_v4.get(job_id)


def dispatch_poll(job_id: str) -> bool:
    with _POLL_LOCK:
        if job_id in _ACTIVE_POLLS:
            return False
        _ACTIVE_POLLS.add(job_id)

    def target() -> None:
        try:
            _poll_existing(job_id)
        finally:
            with _POLL_LOCK:
                _ACTIVE_POLLS.discard(job_id)

    Thread(target=target, name=f"deep-research-{job_id}", daemon=True).start()
    return True


def run(job_id: str) -> ResearchRuntimeV4:
    job = orchestrator_v4.get(job_id)
    job.status = "researching"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="search_and_draft", status="started")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        error = RuntimeError("OPENAI_API_KEY is not configured")
        return _fail(job, error)
    payload = build_request_payload(job)
    try:
        data = _response_request(
            f"{os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')}/responses",
            api_key=api_key, payload=payload,
            timeout=int(os.getenv("LOGISPACE_DEEP_RESEARCH_CREATE_TIMEOUT_SECONDS", "60")),
        )
        _save_response_snapshot(job_id, data)
        job.provider_response_id = data.get("id")
        if not job.provider_response_id:
            raise RuntimeError("OpenAI background response did not include an id")
        repository.save(job)
        if data.get("status") in {"completed", "incomplete"}:
            return _complete_from_response(job, data)
        # Do not poll in this request-creation thread. GET requests may arrive
        # immediately from the UI; dispatch_poll is the single ownership gate
        # for all background status reads.
        dispatch_poll(job_id)
        return job
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return _fail(job, RuntimeError(f"OpenAI API error {error.code}: {detail[:1000]}"))
    except Exception as error:
        return _fail(job, error)


def dispatch_run(job_id: str) -> bool:
    """Dispatch exactly one run from non-HTTP recovery code.

    HTTP handlers should use ``schedule_run`` so FastAPI owns the task
    lifecycle.  This thread-based fallback is kept for persisted-job recovery
    from service code where no request-scoped scheduler exists.
    """
    with _RUN_LOCK:
        if job_id in _ACTIVE_RUNS:
            return False
        _ACTIVE_RUNS.add(job_id)

    def target() -> None:
        try:
            run(job_id)
        finally:
            with _RUN_LOCK:
                _ACTIVE_RUNS.discard(job_id)

    Thread(target=target, name=f"deep-research-create-{job_id}", daemon=True).start()
    return True


def schedule_run(background_tasks: BackgroundTasks, job_id: str) -> bool:
    """Schedule exactly one API-backed run on FastAPI's managed task queue."""
    with _RUN_LOCK:
        if job_id in _ACTIVE_RUNS:
            return False
        _ACTIVE_RUNS.add(job_id)

    def target() -> None:
        try:
            run(job_id)
        finally:
            with _RUN_LOCK:
                _ACTIVE_RUNS.discard(job_id)

    try:
        background_tasks.add_task(target)
    except Exception:
        with _RUN_LOCK:
            _ACTIVE_RUNS.discard(job_id)
        raise
    return True


def _fail(job: ResearchRuntimeV4, error: Exception) -> ResearchRuntimeV4:
    canonical = repository.load(job.job_id)
    if canonical is not None and (canonical.research_report is not None or canonical.status == "completed"):
        return canonical
    snapshot = _response_snapshot_path(job.job_id)
    if snapshot.exists():
        try:
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            if data.get("status") in {"completed", "incomplete"}:
                return _complete_from_response(canonical or job, data)
        except (OSError, json.JSONDecodeError):
            pass
    # Keep the generated plan reusable. A failed provider request returns to
    # the approval screen instead of discarding the plan or dropping the user
    # into the legacy per-unit evidence UI.
    job.status = "awaiting_plan_approval" if job.plan is not None else "failed"
    if job.plan is not None:
        job.plan.approved = False
        for unit in job.plan.units:
            unit.status = "planned"
        job.units = {}
    job.provider_response_id = None
    job.errors.append(str(error))
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="search_and_draft", status="failed", error=str(error))
    return job


def start(request: ResearchJobCreateV4) -> ResearchRuntimeV4:
    return orchestrator_v4.start(request)


def get(job_id: str) -> ResearchRuntimeV4:
    job = orchestrator_v4.get(job_id)
    if job.research_report is not None:
        desired_status = "partially_completed" if job.research_report.incomplete_reason else "completed"
        changed = job.status != desired_status or not job.provider_response_id
        job.status = desired_status
        job.provider_response_id = job.research_report.provider_response_id or job.provider_response_id
        if job.plan is not None and not job.plan.approved:
            job.plan.approved = True
            changed = True
        if changed:
            job.updated_at = datetime.now(timezone.utc)
            repository.save(job)
        return job
    snapshot = _response_snapshot_path(job_id)
    if job.status in {"researching", "failed", "awaiting_plan_approval"} and snapshot.exists():
        try:
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            status = data.get("status")
            if status in {"completed", "incomplete"}:
                return _complete_from_response(job, data)
            if status in {"queued", "in_progress"} and job.provider_response_id:
                job.status = "researching"
                repository.save(job)
                dispatch_poll(job_id)
                return job
        except Exception as error:
            return _fail(job, RuntimeError(f"Saved OpenAI response could not be projected: {error}"))
    if job.status != "researching":
        return job
    if job.provider_response_id:
        dispatch_poll(job_id)
        return job
    timeout = int(os.getenv("LOGISPACE_DEEP_RESEARCH_CREATE_TIMEOUT_SECONDS", "60"))
    age_seconds = (datetime.now(timezone.utc) - job.updated_at).total_seconds()
    if age_seconds > timeout + 30:
        return _fail(job, RuntimeError(
            "Research worker stopped before saving the OpenAI response. Start a new task; this task will not keep polling indefinitely."
        ))
    return job
