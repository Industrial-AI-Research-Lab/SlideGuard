"""
CLI entrypoint for SlideGuard using Typer.

Usage examples:
  - slideguard eval run path/to/presentation.pdf
  - slideguard eval run path/to/presentation.pdf --slide-criteria "Slide Visual Arrangement" \
      --deck-criteria "Deck Structure Analysis" --json-output
"""

from __future__ import annotations

import asyncio
import json
from typing import List, Optional

import typer
from dotenv import load_dotenv
import importlib

from slideguard.config import config
from slideguard.crew.evaluator import SlideGuardEvaluator


def load_environment_variables() -> None:
    """Load environment variables from .env file if it exists."""
    load_dotenv()
    # Enable Langfuse observability via OpenTelemetry (if available)
    try:
        _openlit = importlib.import_module("openlit")
        _openlit.init(service_name="slideguard-cli")
    except Exception:
        pass


app = typer.Typer(help="SlideGuard - Evaluate slide decks with AI")
eval_app = typer.Typer(help="Run evaluations")
app.add_typer(eval_app, name="eval")


def _print_config_help() -> None:
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
    slide_criteria: Optional[List[str]] = typer.Option(
        None,
        "--slide-criteria",
        help="Slide-level criteria names (repeat option to pass multiple)",
    ),
    deck_criteria: Optional[List[str]] = typer.Option(
        None,
        "--deck-criteria",
        help="Deck-level criteria names (repeat option to pass multiple)",
    ),
    slide_types_filter: Optional[List[str]] = typer.Option(
        None,
        "--slide-types-filter",
        help="Filter results to specific slide types (repeat option)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json-output",
        help="Print raw JSON of the final evaluation result",
    ),
    concurrency_limit: int = typer.Option(
        4,
        "--concurrency-limit",
        help="Maximum number of slides to evaluate concurrently",
    ),
) -> None:
    """Start an evaluation for the given presentation."""

    # Load environment variables from .env file
    load_environment_variables()

    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(),
        cache_manager=CacheManager(),
        llm=create_llm_from_env()
    )

    if evaluator.llm is None:
        _print_config_help()
        raise typer.Exit(code=1)

    async def _run():
        return await evaluator.evaluate_presentation(
            presentation_path=presentation_path,
            slide_criteria=slide_criteria,
            deck_criteria=deck_criteria,
            slide_types_filter=slide_types_filter,
            concurrency_limit=concurrency_limit,
        )

    try:
        result = asyncio.run(_run())
    except FileNotFoundError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)
    except Exception as e:
        typer.echo(f"Evaluation failed: {e}")
        raise typer.Exit(code=3)

    if json_output:
        # Pydantic v2 BaseModel
        try:
            payload = result.model_dump()
        except Exception:
            # Fallback for safety
            payload = json.loads(result.json()) if hasattr(result, "json") else result.__dict__
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # Human-friendly summary
    typer.echo(f"Overall score: {result.overall_score}")
    typer.echo(f"Summary: {result.summary}")


def main() -> None:  # Console entrypoint
    app()


if __name__ == "__main__":
    main()


