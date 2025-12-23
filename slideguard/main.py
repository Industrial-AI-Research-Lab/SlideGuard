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

from slideguard.criteria import get_registry_provider
from slideguard.utils.config import SlideGuardConfig, load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.schemes import Criteria, FullEvaluation
from slideguard.utils.config import load_langfuse_client
from slideguard.utils.cache_manager import CacheManager
from slideguard.utils.file_manager import FileManager
from slideguard.ui.app import create_app
from slideguard.ui.auth import (
    verify_user_db,
    init_db,
    register_user,
    Role,
    update_user_password,
    update_user_role,
    delete_user,
    list_users,
)
from slideguard.criteria.types import PresentationType

def _initialize_logging() -> None:
    """Initialize logging configuration for SlideGuard."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    class _DropOtelExportErrors(logging.Filter): # do not show otel export errors (occur from bad connection)
        def filter(self, record: logging.LogRecord) -> bool:
            name = record.name or ""
            msg = record.getMessage() if record.msg is not None else ""
            if name.startswith("opentelemetry") and "Exception while exporting Span" in msg:
                return False
            if name.startswith("opentelemetry") and ("ConnectTimeout" in msg or "Connection to" in msg or "Remote end closed" in msg):
                return False
            return True
    root = logging.getLogger()
    for h in root.handlers:
        h.addFilter(_DropOtelExportErrors())
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry.sdk._shared_internal").setLevel(logging.ERROR)
    logging.getLogger("opentelemetry.exporter").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


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


def _load_criterias(criteria: Optional[List[str]], presentation_type: Optional[str]) -> Tuple[List[Criteria], List[Criteria]]:
    """Load slide and deck criteria based on input criteria list and presentation type."""
    provider = get_registry_provider()
    registry = provider.get_for_user()

    def _validate_applicability(selected: List[Criteria]) -> None:
        if not presentation_type:
            return
        for crit in selected:
            info = registry.get_info(crit)
            if info.presentation_types and presentation_type not in info.presentation_types:
                raise typer.BadParameter(
                    f"Criterion '{crit.value}' is not available for presentation type '{presentation_type}'."
                )

    if criteria:
        criterias = [Criteria(c) for c in criteria]
        slide_criterias = [c for c in criterias if c.is_slide_criteria()]
        deck_criterias = [c for c in criterias if c.is_deck_criteria()]
        _validate_applicability(slide_criterias + deck_criterias)
    else:
        slide_criterias = registry.get_slide_ids(presentation_type=presentation_type)
        deck_criterias = registry.get_deck_ids(presentation_type=presentation_type)
    
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
        except Exception:
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
ui_app = typer.Typer(help="Run Gradio UI")
admin_app = typer.Typer(help="Run Admin CLI: manage user accounts and roles")
app.add_typer(eval_app, name="eval")
app.add_typer(ui_app, name="ui")
app.add_typer(admin_app, name="admin")


@app.callback()
def main_callback() -> None:
    """Initialize logging when the root command is executed."""
    _initialize_logging()
    _setup_console_encoding()


@eval_app.command("list-criterias")
def eval_list_criterias(
    presentation_type: PresentationType = typer.Option(
        PresentationType.SCIENTIFIC,
        "--presentation-type",
        "-t",
        case_sensitive=False,
        help="Filter criteria by presentation type (collaborative, industrial, scientific, technological)",
    ),
) -> None:
    """List all available slide-level and deck-level criteria."""
    typer.echo("SlideGuard - Available Evaluation Criteria")
    typer.echo("=" * 45)
    
    provider = get_registry_provider()
    registry = provider.get_for_user()
    # Slide-level criteria
    typer.echo("\n📊 Slide-Level Criteria:")
    typer.echo("-" * 25)
    for criteria in registry.get_slide_ids(presentation_type=presentation_type):
        typer.echo(f"  • {criteria.value}")
    
    # Deck-level criteria
    typer.echo("\n📋 Deck-Level Criteria:")
    typer.echo("-" * 24)
    for criteria in registry.get_deck_ids(presentation_type=presentation_type):
        typer.echo(f"  • {criteria.value}")
    
    slide_total = len(registry.get_slide_ids(presentation_type=presentation_type))
    deck_total = len(registry.get_deck_ids(presentation_type=presentation_type))
    typer.echo(f"\nTotal: {slide_total} slide criteria, {deck_total} deck criteria")
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
    raise_on_error: bool = typer.Option(
        False,
        "--raise-on-error",
        help="Raise an exception if an error occurs",
    ),
    eval_debug: bool = typer.Option(
        False,
        "--eval-debug",
        help="Enable debug mode (Save graph images)",
    ),
    presentation_type: PresentationType = typer.Option(
        PresentationType.SCIENTIFIC,
        "--presentation-type",
        "-t",
        case_sensitive=False,
        help="Presentation type: collaborative, industrial, scientific (default), technological",
    ),
) -> None:
    """Start an evaluation for the given presentation."""
    typer.echo("Loading settings...")

    slide_criterias, deck_criterias = _load_criterias(criteria, presentation_type.value)

    # Load environment variables from .env file
    config = load_config(max_concurrency)

    langfuse_client = load_langfuse_client(use_langfuse)

    llm = create_llm_from_config(config)

    if llm is None:
        _print_config_help(config)
        raise typer.Exit(code=1)

    provider = get_registry_provider()
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm,
        max_concurrency=config.max_concurrency,
        debug=eval_debug,
        registry_provider=provider,
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
        if raise_on_error:
            raise e
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
    raise_on_error: bool = typer.Option(
        False,
        "--raise-on-error",
        help="Raise an exception if an error occurs",
    ),
    eval_debug: bool = typer.Option(
        False,
        "--eval-debug",
        help="Enable debug mode (Save graph images)",
    ),
    presentation_type: PresentationType = typer.Option(
        PresentationType.SCIENTIFIC,
        "--presentation-type",
        "-t",
        case_sensitive=False,
        help="Presentation type: collaborative, industrial, scientific (default), technological",
    ),
) -> None:
    """Start evaluations for all PDF files in the given folder."""
    typer.echo("Loading settings...")
    
    slide_criterias, deck_criterias = _load_criterias(criteria, presentation_type.value)
    
    # Load environment variables from .env file
    config = load_config(max_concurrency)
    langfuse_client = load_langfuse_client(use_langfuse)
    llm = create_llm_from_config(config)
    
    if llm is None:
        _print_config_help(config)
        raise typer.Exit(code=1)
    
    provider = get_registry_provider()
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm,
        max_concurrency=config.max_concurrency,
        debug=eval_debug,
        registry_provider=provider,
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
        if raise_on_error:
            raise e
        typer.echo(f"Multirun failed: {e}")
        raise typer.Exit(code=4)
    
    # Count results (files are already written by _process_pdf_with_capture)
    successful_count = 0
    failed_count = 0
    
    successful_count = sum(success for _, success in results)
    failed_count = sum(not success for _, success in results)
    
    # Summary
    typer.echo("\nMultirun completed:")
    typer.echo(f"  Successfully processed: {successful_count} PDFs")
    typer.echo(f"  Failed: {failed_count} PDFs")
    typer.echo(f"  Total: {len(results)} PDFs")
    typer.echo(f"  Results written to: {output_path.absolute()}")


@ui_app.command("run")
def ui_run(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to run the UI on",
    ),
    port: int = typer.Option(
        7860,
        "--port",
        help="Port to run the UI on",
    ),
    share: bool = typer.Option(
        False,
        "--share/--no-share",
        help="Share the UI: creates a public link via SSH tunnel",
    ),
    debug: bool = typer.Option(
        False,
        "--debug/--no-debug",
        help="Enable Gradio debug mode: if True, blocks main thread",
    ),
    show_error: bool = typer.Option(
        True,
        "--show-error/--hide-error",
        help="Show/hide error messages in UI",
    ),
    quiet: bool = typer.Option(
        True,
        "--quiet/--no-quiet",
        help="Quiet mode: if True suppresses print statements",
    ),
    show_api: bool = typer.Option(
        False,
        "--show-api/--hide-api",
        help="Show Gradio API docs in UI",
    ),
    theme: str = typer.Option(
        "light",
        "--theme",
        help="Gradio starting theme: light or dark. Can be changed in UI",
    ),
    auth: bool = typer.Option(
        True,
        "--auth/--no-auth",
        help="Enable authentication",
    ),
    use_langfuse: bool = typer.Option(
        False,
        "--use-langfuse",
        help="Use Langfuse for observability",
    ),
    eval_debug: bool = typer.Option(
        False,
        "--eval-debug",
        help="Enable debug mode (Save graph images)",
    ),
) -> None:
    """Run the Gradio UI"""
    header = "=" * 60
    typer.echo(header)
    typer.echo("🚀 Starting SlideGuard UI...")
    typer.echo(header)
    typer.echo("Ensure environment variables or .env are configured.")
    typer.echo(f"Open: http://{host}:{port}?__theme={theme}")
    typer.echo()
    try:
        app = create_app(auth=auth, use_langfuse=use_langfuse, eval_debug=eval_debug)
        auth_func = verify_user_db if auth else None
        app.launch(
            server_name=host,
            server_port=port,
            share=share,
            debug=debug,
            show_error=show_error,
            quiet=quiet,
            show_api=show_api,
            auth=auth_func
        )
    except Exception as e:
        typer.echo(f"❌ Failed to start UI: {e}")
        raise typer.Exit(code=5)


@admin_app.command("create")
def admin_create(
    username: str = typer.Option(
        ...,
        "-u",
        "--username",
        help="Username for the new account",
    ),
    role: Role = typer.Option(
        Role.USER,
        "-r",
        "--role",
        help="Role for the new account",
    ),
) -> None:
    uname = (username or "").strip()
    if not uname:
        typer.echo("Username cannot be empty")
        raise typer.Exit(code=1)
    init_db()
    pw1 = typer.prompt("Password", hide_input=True)
    pw2 = typer.prompt("Confirm", hide_input=True)
    if pw1 != pw2:
        typer.echo("Passwords do not match")
        raise typer.Exit(code=1)
    if not pw1 or not pw1.strip():
        typer.echo("Password cannot be empty")
        raise typer.Exit(code=1)
    ok = register_user(uname, pw1, role)
    typer.echo("Created" if ok else "Username already exists")
    raise typer.Exit(code=0 if ok else 1)


@admin_app.command("pwd")
def admin_pwd(
    username: str = typer.Option(
        ...,
        "-u",
        "--username",
        help="Username to change password for",
    ),
) -> None:
    uname = (username or "").strip()
    if not uname:
        typer.echo("Username cannot be empty")
        raise typer.Exit(code=1)
    init_db()
    pw1 = typer.prompt("New password", hide_input=True)
    pw2 = typer.prompt("Confirm", hide_input=True)
    if pw1 != pw2:
        typer.echo("Passwords do not match")
        raise typer.Exit(code=1)
    if not pw1 or not pw1.strip():
        typer.echo("Password cannot be empty")
        raise typer.Exit(code=1)
    ok = update_user_password(uname, pw1)
    typer.echo("Password updated" if ok else "User not found")
    raise typer.Exit(code=0 if ok else 1)


@admin_app.command("role")
def admin_role(
    username: str = typer.Option(
        ...,
        "-u",
        "--username",
        help="Username to change role for",
    ),
    role: Role = typer.Option(
        Role.USER,
        "-r",
        "--role",
        help="New role to assign",
    ),
) -> None:
    uname = (username or "").strip()
    if not uname:
        typer.echo("Username cannot be empty")
        raise typer.Exit(code=1)
    init_db()
    ok = update_user_role(uname, role)
    typer.echo("Role updated" if ok else "User not found")
    raise typer.Exit(code=0 if ok else 1)


@admin_app.command("delete")
def admin_delete(
    username: str = typer.Option(
        ...,
        "-u",
        "--username",
        help="Username to delete",
    ),
) -> None:
    uname = (username or "").strip()
    if not uname:
        typer.echo("Username cannot be empty")
        raise typer.Exit(code=1)
    init_db()
    ok = delete_user(uname)
    typer.echo("Deleted" if ok else "User not found")
    raise typer.Exit(code=0 if ok else 1)


@admin_app.command("list")
def admin_list() -> None:
    init_db()
    users = list_users()
    if not users:
        typer.echo("No users found in the database")
        raise typer.Exit(code=0)
    for uname, role in users:
        typer.echo(f"{uname}\t{role}")
    raise typer.Exit(code=0)


def main() -> None:  # Console entrypoint
    app()


if __name__ == "__main__":
    main()


