from __future__ import annotations
from uuid import uuid4
from logispace_domain.models import WorkDossier
from logispace_domain.models_v3 import *
TITLES={
 "identity":"\u4f5c\u54c1\u6982\u89c8","characters":"\u6838\u5fc3\u4eba\u7269","relationships":"\u4eba\u7269\u5173\u7cfb","locations_objects":"\u5730\u70b9\u4e0e\u5173\u952e\u7269\u4ef6","timeline_truth":"\u771f\u5b9e\u65f6\u95f4\u7ebf","timeline_investigation":"\u8c03\u67e5\u65f6\u95f4\u7ebf","timeline_narrative":"\u53d9\u4e8b\u65f6\u95f4\u7ebf","clues_testimony":"\u7ebf\u7d22\u4e0e\u8bc1\u8a00","crime_execution":"\u72af\u7f6a\u6267\u884c","murder_method":"\u6740\u4eba\u65b9\u6cd5","trick_misdirection":"\u6838\u5fc3\u8be1\u8ba1\u4e0e\u8bef\u5bfc","solution":"\u89e3\u7b54\u6a21\u578b","creation_background":"\u521b\u4f5c\u80cc\u666f","adaptations":"\u6539\u7f16\u5dee\u5f02","controversies":"\u4e89\u8bae\u4e0e\u8ba8\u8bba"}
def build_report(work:Work,version:str,claims:list[ClaimV3])->ResearchReportV3:
 grouped={}
 for claim in claims:grouped.setdefault(claim.section,[]).append(claim)
 sections=[]
 for section in SECTIONS:
  items=grouped.get(section,[])
  if not items:continue
  paragraphs=[]
  for item in items:
   marker="["+", ".join(item.evidence_ids)+"]" if item.evidence_ids else ""
   paragraphs.append(f"{item.text} {marker}".strip())
  sections.append(ReportSectionV3(section_id=section,title=TITLES.get(section,section),body="\n\n".join(paragraphs),claim_ids=[c.claim_id for c in items],evidence_ids=list(dict.fromkeys(e for c in items for e in c.evidence_ids))))
 summary=f"\u672c\u62a5\u544a\u6839\u636e {len(claims)} \u6761\u5df2\u9a8c\u8bc1 Claim \u6574\u7406\uff0c\u5305\u542b {len(sections)} \u4e2a\u7814\u7a76\u7ae0\u8282\u3002"
 return ResearchReportV3(report_id=f"report_{uuid4().hex[:10]}",work_id=work.work_id,version=version,title=f"\u300a{work.canonical_title}\u300b\u6df1\u5ea6\u7814\u7a76\u62a5\u544a",summary=summary,sections=sections)
def build_package(work:Work,version:str,baseline:WorkDossier,claims:list[ClaimV3])->KnowledgePackageV3:
 characters=[CharacterEntryV3(entity_id=e.entity_id,name=e.name,summary=e.summary,aliases=list(e.attributes.get("aliases",[]))) for e in baseline.entities if e.entity_type in {"Character","CollectiveActor"}]
 relationships=[RelationshipEntryV3(source_id=r.source_id,relation_type=r.relation,target_id=r.target_id,summary=r.note or "") for r in baseline.relations]
 timeline=[]
 for e in baseline.entities:
  track=e.attributes.get("track")
  if track in {"truth","investigation","narrative"}:timeline.append(TimelineEntryV3(event_id=e.entity_id,track=track,order=int(e.attributes.get("order",len(timeline)+1)),title=e.name,summary=e.summary,participant_ids=list(e.attributes.get("participants",[])) if isinstance(e.attributes.get("participants",[]),list) else []))
 tricks=[TrickEntryV3(trick_id=e.entity_id,name=e.name,trick_type=str(e.attributes.get("trick_type","unclassified")),mechanism=e.summary) for e in baseline.entities if e.entity_type=="Trick"]
 methods=[MurderMethodEntryV3(method_id=e.entity_id,name=e.name,method_type=str(e.attributes.get("method_type","unclassified")),execution=e.summary) for e in baseline.entities if e.entity_type=="MurderMethod"]
 for claim in claims:
  if claim.section=="trick_misdirection":tricks.append(TrickEntryV3(trick_id=f"trick_{claim.claim_id}",name=claim.text[:80],mechanism=claim.text,claim_ids=[claim.claim_id],evidence_ids=claim.evidence_ids))
  if claim.section in {"murder_method","crime_execution"}:methods.append(MurderMethodEntryV3(method_id=f"method_{claim.claim_id}",name=claim.text[:80],execution=claim.text,claim_ids=[claim.claim_id],evidence_ids=claim.evidence_ids))
  track={"timeline_truth":"truth","timeline_investigation":"investigation","timeline_narrative":"narrative"}.get(claim.section)
  if track:timeline.append(TimelineEntryV3(event_id=f"event_{claim.claim_id}",track=track,order=1+sum(x.track==track for x in timeline),title=claim.text[:80],summary=claim.text,claim_ids=[claim.claim_id]))
 return KnowledgePackageV3(package_id=f"package_{uuid4().hex[:10]}",work_id=work.work_id,version=version,characters=characters,relationships=relationships,timeline=sorted(timeline,key=lambda x:(x.track,x.order)),tricks=tricks,murder_methods=methods)
