from types import SimpleNamespace

from app.services.projection_v4 import (
    audit_case_file, cross_projection_audit, map_knowledge_proposals, write_case_file,
)
from logispace_domain import dossiers
from logispace_domain.models_v4_projection import CaseFileV4, DossierBlockV4
from logispace_domain.models_v4_verified import VerifiedClaimV4, VerifiedDomainObjectV4, VerifiedKnowledgeSnapshotV4


class WriterLLM:
    available = True

    def respond_json(self, **kwargs):
        blocks = [
            {"layer": "one_minute", "block_type": "summary", "title": "一分钟读懂", "text": "叙述省略构成研究主线。", "claim_ids": ["claim_1"], "evidence_ids": ["ev_1"]},
            {"layer": "core", "block_type": "trick", "title": "诡计剖面", "text": "验证知识显示叙述存在省略。", "claim_ids": ["claim_1"], "evidence_ids": ["ev_1"]},
            {"layer": "appendix", "block_type": "sources", "title": "证据附录", "text": "Exact evidence is linked.", "claim_ids": ["claim_1"], "evidence_ids": ["ev_1"]},
        ]
        return {"research_mainline": "不可靠叙述", "reliability_note": "仅表达已验证知识。", "blocks": blocks}, SimpleNamespace(input_tokens=1, output_tokens=1)


def knowledge():
    return VerifiedKnowledgeSnapshotV4(
        snapshot_id="vk_1", work_id="murder-of-roger-ackroyd", media_version="original_novel",
        claims=[VerifiedClaimV4(
            claim_id="claim_1", text="The narrative omits an action.", claim_type="fact",
            domain="tricks", media_version="original_novel", support_status="supported",
            evidence_ids=["ev_1"],
        )],
        domain_objects=[VerifiedDomainObjectV4(
            object_id="trick_1", object_type="trick", payload={"trick_type": "narrative_omission"},
            claim_ids=["claim_1"],
        )],
        claim_graph=[], conflicts=[], unknowns=[], gaps=[], evidence_ids=["ev_1"],
    )


def test_case_file_and_proposals_are_parallel_verified_knowledge_projections():
    verified = knowledge()
    work = dossiers.get_dossier(verified.work_id).work
    case_file = write_case_file(work=work, knowledge=verified, llm=WriterLLM())
    proposals = map_knowledge_proposals(verified)
    audit = cross_projection_audit(case_file, proposals, verified)
    assert audit.passed
    assert {block.layer for block in case_file.blocks} == {"one_minute", "core", "appendix"}
    assert proposals[0].operation == "add_trick"
    assert proposals[0].claim_ids == ["claim_1"]
    assert proposals[0].evidence_ids == ["ev_1"]


def test_writer_audit_rejects_new_unverified_fact():
    verified = knowledge()
    case_file = CaseFileV4(
        case_file_id="case_bad", work_id=verified.work_id, media_version="original_novel",
        title="Bad", research_mainline="Bad", reliability_note="Bad",
        blocks=[
            DossierBlockV4(block_id="b1", layer="one_minute", block_type="summary", title="Summary", text="A new factual assertion."),
            DossierBlockV4(block_id="b2", layer="core", block_type="analysis", title="Core", text="Known", claim_ids=["claim_1"], evidence_ids=["ev_1"]),
            DossierBlockV4(block_id="b3", layer="appendix", block_type="sources", title="Appendix", text="Sources"),
        ],
    )
    audit = audit_case_file(case_file, verified)
    assert not audit.passed
    assert any("without claim IDs" in issue for issue in audit.issues)


def test_writer_audit_rejects_evidence_not_linked_to_block_claims():
    verified = knowledge()
    case_file = CaseFileV4(
        case_file_id="case_bad_ev", work_id=verified.work_id, media_version="original_novel",
        title="Bad", research_mainline="Bad", reliability_note="Bad",
        blocks=[
            DossierBlockV4(block_id="b1", layer="one_minute", block_type="summary", title="Summary", text="Known", claim_ids=["claim_1"], evidence_ids=["ev_other"]),
            DossierBlockV4(block_id="b2", layer="core", block_type="analysis", title="Core", text="Known", claim_ids=["claim_1"], evidence_ids=["ev_1"]),
            DossierBlockV4(block_id="b3", layer="appendix", block_type="sources", title="Appendix", text="Sources"),
        ],
    )
    assert any("outside its claims" in issue for issue in audit_case_file(case_file, verified).issues)
