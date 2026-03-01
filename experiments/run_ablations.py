#!/usr/bin/env python3
"""
Runner script for SlideGuard ablation experiments.

Runs the evaluation pipeline under four configurations:
  - baseline:       default pipeline (all features enabled)
  - no_filtering:   applicability filtering disabled
  - text_only:      slide criteria receive text descriptions instead of images
  - no_retry:       structured-output retry disabled (max_retries=0)

Results are saved as JSON files under <output-dir>/<ablation>/<pdf_stem>.json.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.criteria import get_registry_provider
from slideguard.criteria.configs import DEFAULT_CRITERIA_CONFIGS
from slideguard.criteria.factory import CriteriaRegistry
from slideguard.criteria.presentation_types import PresentationType
from slideguard.schemes import Criteria, FullEvaluation
from slideguard.utils.cache_manager import CacheManager
from slideguard.utils.config import load_config
from slideguard.utils.file_manager import FileManager

from experiments.ablations.no_filtering import build_no_filtering_registry
from experiments.ablations.text_only import TextOnlyEvaluator
from experiments.ablations.no_retry import create_no_retry_llm

logger = logging.getLogger(__name__)

ALL_ABLATIONS = ["baseline", "no_filtering", "text_only", "no_retry"]


def _find_pdfs(path: str) -> List[Path]:
    p = Path(path)
    if p.is_file() and p.suffix.lower() == ".pdf":
        return [p]
    if p.is_dir():
        return sorted(p.rglob("*.pdf"))
    raise FileNotFoundError(f"No PDF files found at {path}")


def _build_evaluator(
    ablation: str,
    config,
    file_manager: FileManager,
    cache_base: str,
    presentation_type: Optional[PresentationType],
) -> Tuple[SlideGuardEvaluator, Optional[CriteriaRegistry]]:
    """Return (evaluator, optional_override_registry) for the given ablation."""
    cache_dir = os.path.join(cache_base, ablation)
    cache_manager = CacheManager(cache_dir)

    if ablation == "no_retry":
        llm = create_no_retry_llm(config)
    else:
        llm = create_llm_from_config(config)

    if llm is None:
        raise RuntimeError("LLM could not be initialised — check env vars / .env file.")

    provider = get_registry_provider()
    override_registry: Optional[CriteriaRegistry] = None

    if ablation == "no_filtering":
        override_registry = build_no_filtering_registry(
            DEFAULT_CRITERIA_CONFIGS,
            presentation_type=presentation_type,
        )

    evaluator_cls = TextOnlyEvaluator if ablation == "text_only" else SlideGuardEvaluator

    evaluator = evaluator_cls(
        file_manager=file_manager,
        cache_manager=cache_manager,
        llm=llm,
        max_concurrency=config.max_concurrency,
        registry_provider=provider,
    )

    return evaluator, override_registry


async def _run_single(
    evaluator: SlideGuardEvaluator,
    pdf_path: Path,
    slide_criteria: List[Criteria],
    deck_criteria: List[Criteria],
    presentation_type: Optional[PresentationType],
    override_registry: Optional[CriteriaRegistry],
) -> FullEvaluation:
    return await evaluator.evaluate_presentation(
        presentation_path=str(pdf_path),
        slide_criterias=slide_criteria,
        deck_criterias=deck_criteria,
        presentation_type=presentation_type,
        registry=override_registry,
    )


async def run_ablation(
    ablation: str,
    pdfs: List[Path],
    config,
    file_manager: FileManager,
    output_dir: str,
    cache_base: str,
    presentation_type: Optional[PresentationType],
) -> Dict[str, str]:
    """Run one ablation across all PDFs.  Returns {pdf_stem: result_path}."""
    evaluator, override_registry = _build_evaluator(
        ablation, config, file_manager, cache_base, presentation_type,
    )

    provider = get_registry_provider()
    registry = override_registry or provider.get_for_user()
    slide_criteria = registry.get_slide_ids(presentation_type=presentation_type)
    deck_criteria = registry.get_deck_ids(presentation_type=presentation_type)

    abl_dir = os.path.join(output_dir, ablation)
    os.makedirs(abl_dir, exist_ok=True)

    results: Dict[str, str] = {}
    for pdf in pdfs:
        stem = pdf.stem
        out_path = os.path.join(abl_dir, f"{stem}.json")
        logger.info("[%s] evaluating %s …", ablation, stem)
        t0 = time.time()
        try:
            evaluation = await _run_single(
                evaluator, pdf, slide_criteria, deck_criteria,
                presentation_type, override_registry,
            )
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(evaluation.model_dump_json(indent=2))
            elapsed = time.time() - t0
            logger.info("[%s] %s done (%.1fs) -> %s", ablation, stem, elapsed, out_path)
            results[stem] = out_path
        except Exception:
            logger.exception("[%s] %s FAILED", ablation, stem)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SlideGuard ablation experiments")
    parser.add_argument(
        "--pdf-dir", required=True,
        help="Path to a PDF file or directory containing PDF files",
    )
    parser.add_argument(
        "--output-dir", default="experiments/results",
        help="Root directory for result JSONs (default: experiments/results)",
    )
    parser.add_argument(
        "--cache-base", default=".slideguard_ablation_cache",
        help="Root directory for per-ablation evaluation caches",
    )
    parser.add_argument(
        "--ablations", default=",".join(ALL_ABLATIONS),
        help=f"Comma-separated list of ablations to run (choices: {', '.join(ALL_ABLATIONS)})",
    )
    parser.add_argument(
        "--presentation-type", default="scientific",
        choices=[pt.value for pt in PresentationType],
        help="Presentation type for criteria selection (default: scientific)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    ablations = [a.strip() for a in args.ablations.split(",")]
    for a in ablations:
        if a not in ALL_ABLATIONS:
            parser.error(f"Unknown ablation: {a}")

    pdfs = _find_pdfs(args.pdf_dir)
    if not pdfs:
        parser.error(f"No PDFs found at {args.pdf_dir}")
    logger.info("Found %d PDF(s)", len(pdfs))

    presentation_type = PresentationType(args.presentation_type)
    config = load_config()

    file_manager = FileManager(config.file_cache_dir)

    for ablation in ablations:
        logger.info("=== Running ablation: %s ===", ablation)
        asyncio.run(run_ablation(
            ablation=ablation,
            pdfs=pdfs,
            config=config,
            file_manager=file_manager,
            output_dir=args.output_dir,
            cache_base=args.cache_base,
            presentation_type=presentation_type,
        ))

    logger.info("All ablations complete.  Results in %s", args.output_dir)


if __name__ == "__main__":
    main()
