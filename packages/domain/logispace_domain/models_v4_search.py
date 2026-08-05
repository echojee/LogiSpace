from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

SearchLevel = Literal["local", "core_pack", "authority_verification", "adjacent", "open_web"]


class SourceRegistryEntryV4(BaseModel):
    domain: str
    source_family: str
    market: Literal["zh", "en", "bilingual"]
    preferred_for: list[str]
    prohibited_as_sole_support_for: list[str] = Field(default_factory=list)
    access_mode: Literal["html", "api", "pdf", "transcript", "local"] = "html"
    research_value: float = Field(ge=0, le=1)
    evidence_authority: float = Field(ge=0, le=1)
    version_risk: Literal["low", "medium", "high"] = "medium"
    independence_group: str
    locator_strategy: str
    retention_policy: str = "metadata_and_permitted_snapshot"


class SourcePackV4(BaseModel):
    pack_id: str
    domains: list[str] = Field(min_length=1)
    high_priority: list[str] = Field(min_length=1)
    secondary: list[str] = Field(default_factory=list)
    query_templates_zh: list[str] = Field(min_length=1)
    query_templates_en: list[str] = Field(min_length=1)
    max_queries: int = Field(default=4, ge=1, le=10)
    max_hits_per_query: int = Field(default=5, ge=1, le=20)
    max_pages: int = Field(default=6, ge=1, le=20)


class RoutedSourceV4(BaseModel):
    domain: str
    level: SearchLevel
    research_value: float = Field(ge=0, le=1)
    evidence_authority: float = Field(ge=0, le=1)
    source_role: str


class SearchFunnelV4(BaseModel):
    research_unit_id: str
    source_pack_ids: list[str] = Field(min_length=1)
    queries: list[str] = Field(min_length=1)
    routes: list[RoutedSourceV4]
    query_budget_by_level: dict[SearchLevel, int]
    open_web_query_limit: int = Field(ge=0)

    @model_validator(mode="after")
    def open_web_is_last_and_limited(self):
        external = sum(value for level, value in self.query_budget_by_level.items() if level != "local")
        allowed = max(1, int(external * 0.1)) if external else 0
        if self.open_web_query_limit > allowed:
            raise ValueError("open Web may use at most 10% of the external query budget")
        levels = [route.level for route in self.routes]
        if "open_web" in levels and levels[-1] != "open_web":
            raise ValueError("open Web must be the final search level")
        return self
