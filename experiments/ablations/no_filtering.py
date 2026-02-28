"""
Ablation 1: Disable applicability filtering.

Builds a CriteriaRegistry where every CriterionInfo has its slide-type and
infographics applicability constraints removed, so every criterion runs on
every slide regardless of its classified type.
"""

from typing import List, Optional

from slideguard.criteria.factory import CriteriaRegistry, CriteriaRegistryProvider, CriterionConfig
from slideguard.criteria.base import CriterionInfo
from slideguard.criteria.presentation_types import PresentationType


def _strip_slide_applicability(info: CriterionInfo) -> CriterionInfo:
    """Return a copy of *info* with slide-level applicability constraints removed."""
    clone = info.model_copy(deep=True)
    clone.applicable_slide_types = None
    clone.exclude_slide_types = None
    clone.requires_infographics = False
    return clone


def build_no_filtering_registry(
    base_configs: List[CriterionConfig],
    presentation_type: Optional[PresentationType] = None,
) -> CriteriaRegistry:
    """Build a registry that ignores slide-type and infographics constraints.

    Presentation-type filtering is preserved so that the same set of criteria
    is selected; only the per-slide applicability gates are disabled.
    """
    provider = CriteriaRegistryProvider(base_configs)
    base_registry = provider.get_for_user()

    stripped = {
        crit: _strip_slide_applicability(info)
        for crit, info in base_registry.by_id.items()
    }
    return CriteriaRegistry(by_id=stripped)
