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
import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Tuple
from contextlib import redirect_stdout, redirect_stderr, nullcontext
from io import StringIO

import typer
from tqdm.asyncio import tqdm

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


def _setup_console_encoding() -> None:
    """Setup console encoding to handle Unicode characters on Windows."""
    try:
        # Reconfigure stdout and stderr to use UTF-8 encoding
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        # This is a fallback for older Python versions
        os.environ['PYTHONIOENCODING'] = 'utf-8'


def _find_pdf_files(folder_path: str) -> List[Path]:
    """Recursively find all PDF files in the given folder."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    if not folder.is_dir():
        raise ValueError(f"Path is not a directory: {folder_path}")
    
    pdf_files = list(folder.rglob("*.pdf"))
    return pdf_files


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


async def _process_single_presentation(
    presentation_path: str,
    evaluator: SlideGuardEvaluator,
    slide_criterias: List[Criteria],
    deck_criterias: List[Criteria],
    langfuse_client=None
) -> FullEvaluation:
    """Universal function for processing a single presentation.
    
    This function is used by both 'eval run' and 'eval multirun' commands.
    """
    return await evaluator.evaluate_presentation(
        presentation_path=presentation_path,
        slide_criterias=slide_criterias,
        deck_criterias=deck_criterias,
        langfuse_client=langfuse_client
    )


async def _process_pdf_with_capture(
    pdf_path: Path,
    evaluator: SlideGuardEvaluator,
    slide_criterias: List[Criteria],
    deck_criterias: List[Criteria],
    output_folder: Path,
    langfuse_client=None,
    semaphore: asyncio.Semaphore = None
) -> Tuple[str, bool]:
    """Process a single PDF with stdout/stderr capture and write result files directly.
    
    Returns:
        Tuple of (pdf_name, success)
    """
    pdf_name = pdf_path.stem

    json_filepath = output_folder / f"evaluations_{pdf_name}.json"
    stdout_filepath = output_folder / f"evaluations_{pdf_name}.stdout"
    stderr_filepath = output_folder / f"evaluations_{pdf_name}.stderr"
    error_filepath = output_folder / f"evaluations_{pdf_name}.error"
    
    # Capture stdout and stderr
    stdout_capture = StringIO()
    stderr_capture = StringIO()

    result_content = None
    full_error = None
    
    async with semaphore if semaphore else nullcontext():
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                evaluation = await _process_single_presentation(
                    presentation_path=str(pdf_path),
                    evaluator=evaluator,
                    slide_criterias=slide_criterias,
                    deck_criterias=deck_criterias,
                    langfuse_client=langfuse_client
                )
            
            result_content = evaluation.model_dump_json(indent=4)
        except Exception as e:
            full_error = f"Exception:\n{traceback.format_exc()}"
        finally:
            stdout_content = stdout_capture.getvalue()
            stderr_content = stderr_capture.getvalue()

        if result_content is not None:
            with open(json_filepath, "w", encoding="utf-8") as f:
                f.write(result_content)
        else:
            with open(error_filepath, "w", encoding="utf-8") as f:
                f.write(full_error)

        with open(stdout_filepath, "w", encoding="utf-8") as f:
            f.write(stdout_content)

        with open(stderr_filepath, "w", encoding="utf-8") as f:
            f.write(stderr_content)

        return pdf_name, result_content is not None


app = typer.Typer(help="SlideGuard - Evaluate slide decks with AI")
eval_app = typer.Typer(help="Run evaluations")
app.add_typer(eval_app, name="eval")


@app.callback()
def main_callback() -> None:
    """Initialize logging when the root command is executed."""
    _initialize_logging()
    _setup_console_encoding()


@eval_app.command("list-criterias")
def eval_list_criterias() -> None:
    """List all available slide-level and deck-level criteria."""
    typer.echo("SlideGuard - Available Evaluation Criteria")
    typer.echo("=" * 45)
    
    # Slide-level criteria
    typer.echo("\n📊 Slide-Level Criteria:")
    typer.echo("-" * 25)
    for criteria in SLIDE_CRITERIA_INFO.keys():
        typer.echo(f"  • {criteria.value}")
    
    # Deck-level criteria
    typer.echo("\n📋 Deck-Level Criteria:")
    typer.echo("-" * 24)
    for criteria in DECK_CRITERIA_INFO.keys():
        typer.echo(f"  • {criteria.value}")
    
    typer.echo(f"\nTotal: {len(SLIDE_CRITERIA_INFO)} slide criteria, {len(DECK_CRITERIA_INFO)} deck criteria")
    typer.echo("\nUsage examples:")
    typer.echo("  slideguard eval run -p presentation.pdf --criteria slide_visual_arrangement")
    typer.echo("  slideguard eval run -p presentation.pdf --criteria deck_structure_analysis")


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

    typer.echo(f"Starting evaluation for {presentation_path}...")

    try:
        evaluation = asyncio.run(_process_single_presentation(
            presentation_path=presentation_path,
            evaluator=evaluator,
            slide_criterias=slide_criterias,
            deck_criterias=deck_criterias,
            langfuse_client=langfuse_client
        ))
    except FileNotFoundError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)
    except Exception as e:
        typer.echo(f"Evaluation failed: {e}")
        raise typer.Exit(code=3)

    typer.echo(f"Writing results to {output_path}...")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(evaluation.model_dump_json(indent=4))

    # Human-friendly summary
    typer.echo(f"Evaluation is finished. Results have been written to {output_path}")


@eval_app.command("multirun")
def eval_multirun(
    folder_path: str = typer.Option(
        ...,
        "--folder-path",
        "-f",
        help="Path to the folder containing PDF presentations",
    ),
    output_folder: str = typer.Option(
        "multirun_results",
        "--output-folder",
        "-o",
        help="Path to the output folder for results",
    ),
    criteria: Optional[List[str]] = typer.Option(
        None,
        "--criteria",
        help="Slide-level or Deck-level criteria names (repeat option to pass multiple).",
    ),
    deck_concurrency: int = typer.Option(
        3,
        "--deck-concurrency",
        help="Maximum number of presentations to process concurrently",
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
    """Start evaluations for all PDF files in the given folder."""
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
    
    try:
        pdf_files = _find_pdf_files(folder_path)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)
    
    if not pdf_files:
        typer.echo(f"No PDF files found in {folder_path}")
        raise typer.Exit(code=3)
    
    # Create output folder
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Output folder created/verified: {output_path.absolute()}")
    
    typer.echo(f"Found {len(pdf_files)} PDF files to process")
    
    async def _run_multirun():
        semaphore = asyncio.Semaphore(deck_concurrency)
        
        # Create tasks for all PDFs
        tasks = [
            _process_pdf_with_capture(
                pdf_path=pdf_path,
                evaluator=evaluator,
                slide_criterias=slide_criterias,
                deck_criterias=deck_criterias,
                output_folder=output_path,
                langfuse_client=langfuse_client,
                semaphore=semaphore
            )
            for pdf_path in pdf_files
        ]
        
        # Process all PDFs with progress bar
        results = []
        with tqdm(total=len(tasks), desc="Processing PDFs") as pbar:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                pbar.update(1)
        
        return results
    
    try:
        results = asyncio.run(_run_multirun())
    except Exception as e:
        typer.echo(f"Multirun failed: {e}")
        raise typer.Exit(code=4)
    
    # Count results (files are already written by _process_pdf_with_capture)
    successful_count = 0
    failed_count = 0
    
    successful_count = sum(success for _, success in results)
    failed_count = sum(not success for _, success in results)
    
    # Summary
    typer.echo(f"\nMultirun completed:")
    typer.echo(f"  Successfully processed: {successful_count} PDFs")
    typer.echo(f"  Failed: {failed_count} PDFs")
    typer.echo(f"  Total: {len(results)} PDFs")
    typer.echo(f"  Results written to: {output_path.absolute()}")


def main() -> None:  # Console entrypoint
    app()


if __name__ == "__main__":
    main()


