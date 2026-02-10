from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files


def truncate_messages(messages, max_messages=15):
    """
    Truncate message history to prevent context overflow with Gemini API.
    Ensures tool call pairs (AIMessage with tool_calls + ToolMessage) are not split.
    
    Args:
        messages: List of messages from state
        max_messages: Maximum number of messages to keep (default 15)
    
    Returns:
        Truncated list of messages
    """
    if len(messages) <= max_messages:
        return messages
    
    # Always keep the first message (usually the user query)
    first_msg = messages[0]
    
    # We want the 'tail' of the conversation
    # But we must ensure we don't start the tail with an orphaned ToolMessage
    # scan for a safe start index
    potential_start = len(messages) - (max_messages - 1)
    
    # If the message at potential_start is a ToolMessage, skip it and look for the AIMessage before it
    while potential_start < len(messages):
        msg = messages[potential_start]
        # Check if it's a ToolMessage (has tool_call_id property in LangChain)
        is_tool_msg = hasattr(msg, 'tool_call_id') and msg.tool_call_id
        
        # If it's a ToolMessage, it's unsafe to START the tail here 
        # because its corresponding AIMessage (which has the tool_calls) is likely truncated away.
        # So we include the message only if it's NOT a ToolMessage or if we can't find a better start.
        if not is_tool_msg:
            break
        potential_start += 1
        
    # If we skipped too many and have almost no messages left, 
    # just take the last few even if it's risky, or fallback to simple truncation
    if potential_start >= len(messages) - 2:
        return [first_msg] + messages[-(max_messages - 1):]
        
    return [first_msg] + messages[potential_start:]


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]
        
        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]
        
        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")
        
        return {"messages": removal_operations + [placeholder]}
    
    return delete_messages

        