"""
CLI entrypoint for SlideGuard using Typer.

Usage examples:
  - slideguard eval run path/to/presentation.pdf
  - slideguard eval run path/to/presentation.pdf --slide-criteria "Slide Visual Arrangement" \
      --deck-criteria "Deck Structure Analysis" --json-output
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

import typer

from slideguard.utils.config import SlideGuardConfig, load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.schemes import FullEvaluation
from slideguard.utils.config import load_langfuse_client
from slideguard.utils.cache_manager import CacheManager
from slideguard.utils.file_manager import FileManager


app = typer.Typer(help="SlideGuard - Evaluate slide decks with AI")
eval_app = typer.Typer(help="Run evaluations")
app.add_typer(eval_app, name="eval")


def _print_config_help(config: SlideGuardConfig) -> None:
    typer.echo("LLM not available. Configure environment variables or .env file.")
    config.print_config_status()
    typer.echo(
        "To create a .env template run: python -m slideguard.setup setup\n"
        "To test configuration run: python -m slideguard.setup test"
    )


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
    slide_criteria: Optional[List[str]] = typer.Option(
        None,
        "--slide-criteria",
        help="Slide-level criteria names (repeat option to pass multiple).",
    ),
    deck_criteria: Optional[List[str]] = typer.Option(
        None,
        "--deck-criteria",
        help="Deck-level criteria names (repeat option to pass multiple)",
    ),
    max_concurrency: int = typer.Option(
        4,
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
            slide_criterias=slide_criteria,
            deck_criterias=deck_criteria,
            langfuse_client=langfuse_client
        )

    try:
        evaluation = asyncio.run(_run())
    except FileNotFoundError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)
    except Exception as e:
        typer.echo(f"Evaluation failed: {e}")
        raise typer.Exit(code=3)

    with open(output_path, "w") as f:
        f.write(evaluation.model_dump_json())

    # Human-friendly summary
    typer.echo(f"Evaluation is finished. Results have been written to {output_path}")


def main() -> None:  # Console entrypoint
    app()


if __name__ == "__main__":
    main()


