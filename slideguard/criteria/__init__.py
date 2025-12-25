from slideguard.criteria.factory import CriteriaRegistry, CriteriaRegistryProvider
from slideguard.criteria.configs import DEFAULT_CRITERIA_CONFIGS


_default_provider = CriteriaRegistryProvider(DEFAULT_CRITERIA_CONFIGS)
_default_registry = _default_provider.get_for_user()


def get_registry_provider() -> CriteriaRegistryProvider:
    return _default_provider


def get_default_registry() -> CriteriaRegistry:
    return _default_registry