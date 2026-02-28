"""
Ablation 3: Disable structured-output retry.

Creates a ControlledLLM with max_retries=0 so that format instructions are
still appended (the LLM sees the expected JSON schema) but no error-feedback
retry loop is executed on parse failure.  Any parse failure on the first
attempt falls through to the fallback result, quantifying how often the retry
mechanism rescues outputs.
"""

from typing import Optional

from slideguard.crew.controlled_llm import (
    AppLanguage,
    ControlledLLM,
    create_llm_from_config,
)
from slideguard.utils.config import SlideGuardConfig


def create_no_retry_llm(
    config: SlideGuardConfig,
    language: AppLanguage = AppLanguage.EN,
) -> Optional[ControlledLLM]:
    """Build a ControlledLLM identical to the default except max_retries=0."""
    llm = create_llm_from_config(config, language=language)
    if llm is None:
        return None
    llm.max_retries = 0
    return llm
