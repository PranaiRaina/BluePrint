"""Utility functions for CalcAgent including retry logic."""

import asyncio
from typing import Any
from agents import Runner
from openai import BadRequestError


async def run_with_retry(agent: Any, query: str, max_retries: int = 3, retry_delay: float = 1.0) -> Any:
    """
    Run an agent with retry logic for tool calling errors.
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            result = await Runner.run(agent, query)
            return result
        except BadRequestError as e:
            last_exception = e
            error_msg = str(e)
            
            if "tool_use_failed" in error_msg or "Failed to parse" in error_msg:
                if attempt < max_retries - 1:
                    print(f"Tool call failed (attempt {attempt + 1}/{max_retries}), retrying...")
                    await asyncio.sleep(retry_delay)
                    continue
            else:
                raise
        except Exception as e:
            raise
    
    raise last_exception
