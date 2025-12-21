from typing import List, Optional, Type, Dict
import sys
from pydantic import BaseModel, Field, create_model

from slideguard.schemes import Criteria
from slideguard.criteria.base import CriterionInfo, BaseAttributes
from slideguard.criteria.types import (
    CriteriaTarget,
    OutputKind,
    OutputSpec,
    Applicability,
    ScoredListItemSpec,
    PostProcessorFunc,
)


class CriterionConfig(BaseModel):
    id: Criteria
    target: CriteriaTarget
    description: str
    agent_prompt_template: str
    task_prompt_template: str
    output_model: Optional[Type[BaseModel]] = None
    output: OutputSpec = Field(default_factory=OutputSpec)
    priority: int = 1
    category: str = "general"
    applicability: Applicability = Field(default_factory=Applicability)
    postprocessor_funcs: List[PostProcessorFunc] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def _build_scored_list_models(self) -> Type[BaseModel]:
        spec = self.output.item_spec or ScoredListItemSpec()
        item_fields = {
            spec.element_field_name: (str, Field(description=spec.element_description)),
            spec.suggestion_field_name: (str, Field(description=spec.suggestion_description)),
            **{k: (t, f) for k, (t, f) in (spec.extra_item_fields or {}).items()},
        }
        item_name = f"{self.id.name.title().replace('_', '')}Item"
        ItemModel = create_model(
            item_name,
            __base__=BaseAttributes,
            **item_fields,
        )
        container_name = f"{self.id.name.title().replace('_', '')}Result"
        ContainerModel = create_model(
            container_name,
            evaluation_results=(List[ItemModel], Field(description="List of analysis items")),
            score=(int, Field(ge=spec.score_min, le=spec.score_max, description="Overall score")),
        )
        ItemModel.__module__ = __name__
        ContainerModel.__module__ = __name__
        setattr(sys.modules[__name__], item_name, ItemModel)
        setattr(sys.modules[__name__], container_name, ContainerModel)
        return ContainerModel

    def to_info(self) -> CriterionInfo:
        if self.output.kind == OutputKind.custom:
            if not self.output_model:
                raise ValueError(f"Custom output requires output_model for {self.id}")
            out_model = self.output_model
        else:
            out_model = self._build_scored_list_models()

        a = self.applicability
        info = CriterionInfo(
            criteria=self.id,
            type=self.target,
            criterion_description=self.description,
            agent_prompt_template=self.agent_prompt_template,
            task_prompt_template=self.task_prompt_template,
            pydantic=out_model,
            applicable_slide_types=a.applicable_slide_types,
            exclude_slide_types=a.exclude_slide_types,
            priority=self.priority,
            requires_infographics=a.requires_infographics,
            category=self.category,
            postprocessors=self.postprocessor_funcs,
        )
        return info


class CriteriaRegistry(BaseModel):
    by_id: Dict[Criteria, CriterionInfo]

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_infos(cls, infos: List[CriterionInfo]) -> "CriteriaRegistry":
        return cls(by_id={i.criteria: i for i in infos})

    def get_info(self, crit: Criteria) -> CriterionInfo:
        return self.by_id[crit]

    def get_slide_ids(self, include_service: bool = False) -> List[Criteria]:
        ids = [c for c, i in self.by_id.items() if i.type == CriteriaTarget.slide]
        return ids if include_service else [c for c in ids if not c.is_service_criteria()]

    def get_deck_ids(self, include_service: bool = False) -> List[Criteria]:
        ids = [c for c, i in self.by_id.items() if i.type == CriteriaTarget.deck]
        return ids if include_service else [c for c in ids if not c.is_service_criteria()]


class RegistryScope(BaseModel):
    user_id: Optional[str] = None
    overrides: List[CriterionConfig] = Field(default_factory=list)


class CriteriaRegistryProvider:
    def __init__(self, base_configs: List[CriterionConfig]):
        self._base_configs = base_configs
        self._cache: Dict[str, CriteriaRegistry] = {}

    def build(self, scope: RegistryScope) -> CriteriaRegistry:
        conf_map: Dict[Criteria, CriterionConfig] = {c.id: c for c in self._base_configs}
        for oc in scope.overrides:
            if not oc.id.is_service_criteria():
                conf_map[oc.id] = oc
        infos = [c.to_info() for c in conf_map.values()]
        return CriteriaRegistry.from_infos(infos)

    def get_for_user(self, user_id: Optional[str] = None, overrides: Optional[List[CriterionConfig]] = None) -> CriteriaRegistry:
        if not user_id and not overrides:
            key = "__default__"
        else:
            key = f"user::{user_id or 'anon'}::{len(overrides or [])}"
        if key not in self._cache:
            self._cache[key] = self.build(RegistryScope(user_id=user_id, overrides=overrides or []))
        return self._cache[key]

