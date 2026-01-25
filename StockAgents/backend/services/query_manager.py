from typing import Dict, Any
from .agent_engine import agent_engine

class QueryManager:
    def __init__(self):
        pass

    async def process_query(self, query: str, user_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Route the query to the Agentic Engine.
        In the future, this could route to RAG or specific sub-services directly.
        """
        if context is None:
            context = {}
            
        # Add user_id to context
        context['user_id'] = user_id
        
        # Determine strict routing if needed, else default to Agent
        # For now, everything goes through the Agent
        response = await agent_engine.run_workflow(query, context)
        
        return response

query_manager = QueryManager()
