"""Utility functions for CalcAgent including retry logic."""

import asyncio
from typing import Any
from agents import Runner
from openai import BadRequestError


async def run_with_retry(
    agent: Any, query: str, max_retries: int = 3, retry_delay: float = 1.0
) -> Any:
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
                    print(
                        f"Tool call failed (attempt {attempt + 1}/{max_retries}), retrying..."
                    )
                    await asyncio.sleep(retry_delay)
                    continue
            else:
                raise
        except Exception:
            raise

    raise last_exception


async def run_with_retry_stream(
    agent: Any, query: str, max_retries: int = 3, retry_delay: float = 1.0
):
    """
    Run an agent with retry logic for tool calling errors, yielding events.
    Yields:
        {"type": "token", "content": "..."}
        {"type": "status", "content": "..."}
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            # Runner.run_streamed returns a RunResultStreaming object
            # We need to iterate over its stream_events()
            from agents import Runner

            # Note: We need to create a new runner/stream for each attempt
            # The library usage is Runner.run_streamed(agent, input=query)
            # It returns a sync object (RunResultStreaming) whose stream_events() method returns an async generator

            run_result = Runner.run_streamed(agent, input=query)

            async for event in run_result.stream_events():
                # Map library events to our internal event format
                # event is likely a Dataclass (StreamEvent), use getattr to be safe
                event_type = getattr(event, "type", None)

                # Check for Token (Raw Response)
                if event_type == "raw_response_event":
                    # event.data is TResponseStreamEvent
                    data = event.data

                    try:
                        # Handle agents library specific events (ResponseTextDeltaEvent)
                        if getattr(data, "type", "") == "response.output_text.delta":
                            content = getattr(data, "delta", None)
                            if content:
                                yield {"type": "token", "content": content}

                        # Handle Standard OpenAI Object access (Fallback)
                        elif hasattr(data, "choices") and data.choices:
                            delta = data.choices[0].delta
                            if delta.content:
                                yield {"type": "token", "content": delta.content}
                        # Fallback for Dict access
                        elif isinstance(data, dict):
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield {"type": "token", "content": content}
                    except Exception:
                        pass

                # Check for Tool Calls (Status)
                elif event_type == "run_item_stream_event":
                    # We want to notify "Thinking" or "Tool Call"
                    if getattr(event, "name", "") == "tool_called":
                        # event.item is ToolCallItem
                        item = event.item
                        tool_name = "tool"

                        # Extract tool name from object or dict
                        if hasattr(item, "function"):
                            # item.function might be object or dict
                            func = item.function
                            if hasattr(func, "name"):
                                tool_name = func.name
                            elif isinstance(func, dict):
                                tool_name = func.get("name", "tool")
                        elif isinstance(item, dict):
                            tool_name = item.get("function", {}).get("name", "tool")

                        yield {
                            "type": "status",
                            "content": f"Using tool: {tool_name}...",
                        }

            # If we finish the stream successfully, we return (stop yielding)
            return

        except BadRequestError as e:
            last_exception = e
            error_msg = str(e)

            if "tool_use_failed" in error_msg or "Failed to parse" in error_msg:
                if attempt < max_retries - 1:
                    yield {
                        "type": "status",
                        "content": f"Parsing error, retrying ({attempt + 1}/{max_retries})...",
                    }
                    await asyncio.sleep(retry_delay)
                    continue
            else:
                raise
        except Exception:
            raise

    raise last_exception
