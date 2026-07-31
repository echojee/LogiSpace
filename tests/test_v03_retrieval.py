from app.services.retrieval import chunk_snapshot,rank
from app.services.search_providers import SearchHit,score
from logispace_domain.models_v3 import SnapshotV3

def test_source_scoring_prefers_title_match_and_quality_domain():
    good=SearchHit("https://example.edu/paper","罗杰疑案文本研究","阿加莎·克里斯蒂","fixture")
    bad=SearchHit("https://spam.test/category/all","无关页面","聚合内容","fixture")
    assert score(good,"罗杰疑案","novel")>score(bad,"罗杰疑案","novel")

def test_chinese_bm25_retrieves_relevant_chunk():
    text="罗杰疑案中的叙述者通过省略关键行动误导读者。这个段落讨论叙事诡计与叙述可靠性。"*4+"\n"+"另一段只讨论出版信息和封面设计。"*8
    snap=SnapshotV3(snapshot_id="s",source_id="source",url="https://example.test",content_hash="h",content_path="x",content=text,fetch_status="fetched")
    chunks=chunk_snapshot(snap,min_chars=20,max_chars=180)
    result=rank(chunks,"叙述者如何利用叙事诡计误导读者",3)
    assert result and "叙述" in result[0].chunk.content

def test_exact_quote_validation_rejects_model_hallucination(monkeypatch):
    from app.services import research_extractor
    from app.services.retrieval import Chunk,RankedChunk
    from logispace_domain.models_v3 import PlanItemV3
    monkeypatch.setattr(research_extractor.gateway,"api_key","recorded")
    class Result: input_tokens=10;output_tokens=10
    monkeypatch.setattr(research_extractor.gateway,"respond_json",lambda **kwargs:([{"section":"identity","claim_text":"invented","claim_type":"fact","evidence":[{"chunk_id":"c","quote":"text not present in source"}]}],Result()))
    chunk=Chunk("c","snap","source",{"paragraph_start":1},"The actual source body contains a different statement.")
    evidence,claims,usage=research_extractor.extract("Work","novel",[PlanItemV3(section="identity",question="identity",queries=["q"])],{"identity":[RankedChunk(chunk,2.0)]})
    assert evidence==[] and claims==[] and usage["model_calls"]==1
