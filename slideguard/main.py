"""
CLI entrypoint for SlideGuard using Typer.

Usage examples:
  - slideguard eval run path/to/presentation.pdf
  - slideguard eval run path/to/presentation.pdf --slide-criteria "Slide Visual Arrangement" \
      --deck-criteria "Deck Structure Analysis" --json-output
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Tuple

import typer

from slideguard.criteria import DECK_CRITERIA_INFO, SLIDE_CRITERIA_INFO
from slideguard.utils.config import SlideGuardConfig, load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.schemes import Criteria, FullEvaluation
from slideguard.utils.config import load_langfuse_client
from slideguard.utils.cache_manager import CacheManager
from slideguard.utils.file_manager import FileManager


def _initialize_logging() -> None:
    """Initialize logging configuration for SlideGuard."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


app = typer.Typer(help="SlideGuard - Evaluate slide decks with AI")
eval_app = typer.Typer(help="Run evaluations")
app.add_typer(eval_app, name="eval")


@app.callback()
def main_callback() -> None:
    """Initialize logging when the root command is executed."""
    _initialize_logging()


def _print_config_help(config: SlideGuardConfig) -> None:
    typer.echo("LLM not available. Configure environment variables or .env file.")
    config.print_config_status()
    typer.echo(
        "To create a .env template run: python -m slideguard.setup setup\n"
        "To test configuration run: python -m slideguard.setup test"
    )


def _load_criterias(criteria: Optional[List[str]]) -> Tuple[List[Criteria], List[Criteria]]:
    """Load slide and deck criteria based on input criteria list."""
    if criteria:
        criterias = [Criteria(c) for c in criteria]
        slide_criterias = [c for c in criterias if c.is_slide_criteria()]
        deck_criterias = [c for c in criterias if c.is_deck_criteria()]
    else:
        slide_criterias = list(SLIDE_CRITERIA_INFO.keys())
        deck_criterias = list(DECK_CRITERIA_INFO.keys())
    
    return slide_criterias, deck_criterias


@eval_app.command("run")
def eval_run(
    presentation_path: str = typer.Option(
        ...,
        "--presentation-path",
        "-p",
        help="Path to the presentation file (PDF)",
    ),
    output_path: str = typer.Option(
        "evaluation.json",
        "--output-path",
        "-o",
        help="Path to the output file",
    ),
    criteria: Optional[List[str]] = typer.Option(
        None,
        "--criteria",
        help="Slide-level or Deck-level criteria names (repeat option to pass multiple).",
    ),
    max_concurrency: Optional[int] = typer.Option(
        None,
        "--max-concurrency",
        help="Maximum number of requests to send to the LLM simultaneously",
    ),
    use_langfuse: bool = typer.Option(
        False,
        "--use-langfuse",
        help="Use Langfuse for observability",
    ),
) -> None:
    """Start an evaluation for the given presentation."""
    typer.echo(f"Loading settings...")

    slide_criterias, deck_criterias = _load_criterias(criteria)

    # Load environment variables from .env file
    config = load_config(max_concurrency)

    langfuse_client = load_langfuse_client(use_langfuse)

    llm = create_llm_from_config(config)

    if llm is None:
        _print_config_help(config)
        raise typer.Exit(code=1)

    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm
    )

    async def _run() -> FullEvaluation:
        return await evaluator.evaluate_presentation(
            presentation_path=presentation_path,
            slide_criterias=slide_criterias,
            deck_criterias=deck_criterias,
            langfuse_client=langfuse_client
        )

    typer.echo(f"Starting evaluation for {presentation_path}...")

    try:
        evaluation = asyncio.run(_run())
    except FileNotFoundError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)
    except Exception as e:
        typer.echo(f"Evaluation failed: {e}")
        raise typer.Exit(code=3)

    typer.echo(f"Writing results to {output_path}...")

    with open(output_path, "w") as f:
        f.write(evaluation.model_dump_json(indent=4))

    # Human-friendly summary
    typer.echo(f"Evaluation is finished. Results have been written to {output_path}")


def main() -> None:  # Console entrypoint
    app()


if __name__ == "__main__":
    main()


