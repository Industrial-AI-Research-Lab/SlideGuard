"""
Base utilities for SlideGuard.
"""

from dataclasses import dataclass
import logging
import time
from contextlib import contextmanager
from typing import Generator, Optional


logger = logging.getLogger(__name__)


@dataclass
class ExecutionTimerResult:
    execution_time: float


@contextmanager
def timer(operation_name: str, log_level: int = logging.INFO) -> Generator[ExecutionTimerResult, None, None]:
    """
    Context manager for measuring execution time with access to timing results.
    
    Args:
        operation_name: Name of the operation being timed
        log_level: Logging level to use (default: INFO)
        
    Yields:
        dict: Dictionary that will contain 'execution_time' after completion
        
    Example:
        with execution_timer_with_result("Processing slides") as timer:
            # Your code here
            process_slides()
            
        print(f"Took {timer['execution_time']:.2f} seconds")
    """
    start_time = time.perf_counter()
    logger.log(log_level, f"{operation_name} started")
    
    timer_result = ExecutionTimerResult(execution_time=0)
    
    try:
        yield timer_result
    finally:
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        timer_result.execution_time = execution_time
        logger.log(log_level, f"{operation_name} completed in {execution_time:.2f} seconds")
