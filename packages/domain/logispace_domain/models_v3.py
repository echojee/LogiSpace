from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field
from logispace_domain.models import MediaType, SpoilerLevel, Work, WorkDossier

SECTIONS = ["identity","characters","relationships","locations_objects","timeline_truth","timeline_investigation","timeline_narrative","clues_testimony","crime_execution","murder_method","trick_misdirection","solution","creation_background","adaptations","controversies"]

class BudgetV3(BaseModel):
    max_search_rounds:int=Field(2,ge=1,le=10); max_queries:int=Field(20,ge=1,le=100); max_queries_per_section:int=Field(3,ge=1,le=10)
    max_search_hits_per_query:int=Field(10,ge=1,le=30); max_pages_to_fetch_per_query:int=Field(3,ge=1,le=10); max_sources:int=Field(15,ge=1,le=50)
    max_evidence_chunks_per_question:int=Field(6,ge=1,le=20); max_model_calls:int=Field(6,ge=0,le=20); max_model_tokens:int=Field(50000,ge=1000)
class CoverageV3(BaseModel):
    section:str; status:Literal["sufficient","needs_evidence","missing","conflicted","not_applicable"]; structure_count:int=0; evidence_count:int=0; source_count:int=0; average_source_quality:float=0; conflict_count:int=0; knowledge_gaps:list[str]=Field(default_factory=list)
class PlanItemV3(BaseModel):
    section:str; question:str; priority:int=Field(3,ge=1,le=5); queries:list[str]=Field(default_factory=list); preferred_sources:list[str]=Field(default_factory=list); minimum_sources:int=Field(2,ge=1,le=5); enabled:bool=True
class ResearchPlanV3(BaseModel):
    items:list[PlanItemV3]; estimated_queries:int; estimated_sources:int; estimated_model_tokens:int; approved:bool=False
class ResearchJobCreateV3(BaseModel):
    work_id:str|None=None; work:Work|None=None; resolution_id:str|None=None; research_scope:str="incremental_full"; spoiler_level:SpoilerLevel=SpoilerLevel.FULL; budget:BudgetV3=Field(default_factory=BudgetV3); source_urls:list[str]=Field(default_factory=list)
class PlanApprovalV3(BaseModel):
    items:list[PlanItemV3]|None=None
class SearchHitV3(BaseModel):
    url:str; title:str; snippet:str=""; provider:str; score:float=Field(ge=0,le=1); query:str=""
class SourceV3(BaseModel):
    source_id:str; url:str; title:str; source_type:str="web"; media_version:str="selected"; credibility:float=Field(.5,ge=0,le=1)
class SnapshotV3(BaseModel):
    snapshot_id:str; source_id:str; url:str; content_hash:str; content_path:str; content:str=""; fetch_status:Literal["fetched","cached","failed"]; captured_at:datetime=Field(default_factory=datetime.utcnow); error:str|None=None
class EvidenceV3(BaseModel):
    evidence_id:str; snapshot_id:str; source_id:str; section:str; locator:dict[str,Any]; quote:str; relevance_score:float=Field(ge=0,le=1)
class ClaimV3(BaseModel):
    claim_id:str; section:str; text:str; claim_type:Literal["fact","inference","interpretation"]="fact"; evidence_ids:list[str]; support_status:Literal["supported","partially_supported","inferred","conflicted","unsupported"]; spoiler_level:SpoilerLevel=SpoilerLevel.FULL; media_version:str="selected"
class ProposalV3(BaseModel):
    proposal_id:str; operation:Literal["add_entity","add_relation","add_timeline_event","add_claim","flag_conflict"]; target_section:str; summary:str; payload:dict[str,Any]; claim_ids:list[str]; evidence_ids:list[str]; review_status:Literal["pending","approved","rejected"]="pending"
class ReportSectionV3(BaseModel):
    section_id:str; title:str; body:str; claim_ids:list[str]=Field(default_factory=list); evidence_ids:list[str]=Field(default_factory=list); spoiler_level:SpoilerLevel=SpoilerLevel.FULL
class ResearchReportV3(BaseModel):
    report_id:str; work_id:str; version:str; title:str; summary:str; sections:list[ReportSectionV3]=Field(default_factory=list)
class CharacterEntryV3(BaseModel):
    entity_id:str; name:str; summary:str; aliases:list[str]=Field(default_factory=list); claim_ids:list[str]=Field(default_factory=list)
class RelationshipEntryV3(BaseModel):
    source_id:str; relation_type:str; target_id:str; summary:str=""; claim_ids:list[str]=Field(default_factory=list)
class TimelineEntryV3(BaseModel):
    event_id:str; track:Literal["truth","investigation","narrative"]; order:int; title:str; summary:str; participant_ids:list[str]=Field(default_factory=list); claim_ids:list[str]=Field(default_factory=list)
class TrickEntryV3(BaseModel):
    trick_id:str; name:str; trick_type:str="unclassified"; mechanism:str; misdirected_party:str="reader"; reveal:str=""; claim_ids:list[str]=Field(default_factory=list); evidence_ids:list[str]=Field(default_factory=list)
class MurderMethodEntryV3(BaseModel):
    method_id:str; name:str; method_type:str="unclassified"; execution:str; concealment:str=""; detection_breakthrough:str=""; claim_ids:list[str]=Field(default_factory=list); evidence_ids:list[str]=Field(default_factory=list)
class KnowledgePackageV3(BaseModel):
    package_id:str; work_id:str; version:str; characters:list[CharacterEntryV3]=Field(default_factory=list); relationships:list[RelationshipEntryV3]=Field(default_factory=list); timeline:list[TimelineEntryV3]=Field(default_factory=list); tricks:list[TrickEntryV3]=Field(default_factory=list); murder_methods:list[MurderMethodEntryV3]=Field(default_factory=list)
class ReviewV3(BaseModel): approved_proposal_ids:list[str]=Field(default_factory=list); rejected_proposal_ids:list[str]=Field(default_factory=list)
class UsageV3(BaseModel): search_rounds:int=0; queries:int=0; sources:int=0; pages_fetched:int=0; model_calls:int=0; input_tokens:int=0; output_tokens:int=0; model_tokens:int=0
class EventV3(BaseModel): sequence:int; status:str; detail:str; created_at:datetime=Field(default_factory=datetime.utcnow)
class JobV3(BaseModel):
    job_id:str; work:Work; base_version:str; target_version:str; status:Literal["created","awaiting_identity_confirmation","inventorying","planning","awaiting_plan_approval","searching","reading","extracting","verifying","proposing","reflecting","drafting","needs_review","partially_completed","budget_exhausted","published","failed","paused","cancelled","retrying"]
    budget:BudgetV3; usage:UsageV3=Field(default_factory=UsageV3); coverage:list[CoverageV3]=Field(default_factory=list); plan:ResearchPlanV3|None=None; search_hits:list[SearchHitV3]=Field(default_factory=list); sources:list[SourceV3]=Field(default_factory=list); snapshots:list[SnapshotV3]=Field(default_factory=list); evidence:list[EvidenceV3]=Field(default_factory=list); claims:list[ClaimV3]=Field(default_factory=list); proposals:list[ProposalV3]=Field(default_factory=list); report:ResearchReportV3|None=None; knowledge_package:KnowledgePackageV3|None=None; draft:WorkDossier|None=None; diff:dict[str,Any]=Field(default_factory=dict); errors:list[str]=Field(default_factory=list); source_urls:list[str]=Field(default_factory=list); created_at:datetime=Field(default_factory=datetime.utcnow); updated_at:datetime=Field(default_factory=datetime.utcnow)
