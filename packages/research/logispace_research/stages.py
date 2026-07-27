from typing import Protocol

from logispace_domain.models import EvidenceItem, SourceDocument


class Planner(Protocol):
    def plan(self, work_id: str) -> list[str]:
        ...


class Collector(Protocol):
    def collect(self, queries: list[str]) -> list[SourceDocument]:
        ...


class Extractor(Protocol):
    def extract(self, source: SourceDocument) -> list[EvidenceItem]:
        ...


class Verifier(Protocol):
    def verify(self, evidence: list[EvidenceItem]) -> bool:
        ...
