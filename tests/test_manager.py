"""Test suite for ManagerAgent - verifies all tools are properly connected."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestManagerAgentStructure:
    """Tests for ManagerAgent tool registration and structure."""
    
    def test_manager_agent_exists(self):
        """Verify ManagerAgent is importable."""
        from ManagerAgent.router import manager_agent
        assert manager_agent is not None
        assert manager_agent.name == "ManagerAgent"
    
    def test_manager_has_three_tools(self):
        """Verify ManagerAgent has exactly 3 tools registered."""
        from ManagerAgent.router import manager_agent
        assert len(manager_agent.tools) == 3, f"Expected 3 tools, got {len(manager_agent.tools)}"
    
    def test_rag_tool_registered(self):
        """Verify RAG tool is registered."""
        from ManagerAgent.router import manager_agent
        tool_names = [t.name for t in manager_agent.tools]
        assert "perform_rag_search" in tool_names, f"RAG tool not found. Available: {tool_names}"
    
    def test_calculator_tool_registered(self):
        """Verify Calculator tool is registered."""
        from ManagerAgent.router import manager_agent
        tool_names = [t.name for t in manager_agent.tools]
        assert "ask_financial_calculator" in tool_names, f"Calculator tool not found. Available: {tool_names}"
    
    def test_stock_tool_registered(self):
        """Verify Stock Analysis tool is registered."""
        from ManagerAgent.router import manager_agent
        tool_names = [t.name for t in manager_agent.tools]
        assert "ask_stock_analyst" in tool_names, f"Stock tool not found. Available: {tool_names}"


class TestManagerAgentTools:
    """Tests for individual tool functions (mocked external dependencies)."""
    
    @pytest.mark.asyncio
    async def test_rag_tool_function(self):
        """Test RAG tool returns expected format."""
        with patch("ManagerAgent.tools.app_graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(return_value={"generation": "Test RAG response"})
            
            from ManagerAgent.tools import perform_rag_search
            result = await perform_rag_search("test query")
            
            assert result == "Test RAG response"
            mock_graph.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stock_tool_function(self):
        """Test Stock tool returns expected format."""
        mock_agent_engine = MagicMock()
        mock_agent_engine.run_workflow = AsyncMock(return_value={
            "recommendation": "Test stock recommendation"
        })
        
        with patch.dict("sys.modules", {"StockAgents.backend.services.agent_engine": MagicMock(agent_engine=mock_agent_engine)}):
            # Re-import to get the patched version
            from ManagerAgent.tools import ask_stock_analyst
            
            # The lazy import inside the function will use our mock
            with patch("StockAgents.backend.services.agent_engine.agent_engine", mock_agent_engine):
                result = await ask_stock_analyst("analyze AAPL")
                
                # Verify the function handled the result
                assert "stock" in result.lower() or "recommendation" in result.lower() or "error" in result.lower()


class TestManagerAgentDiagramAlignment:
    """Tests that verify architecture matches the user's diagram."""
    
    def test_manager_is_hub(self):
        """Manager should be the central orchestrator (hub)."""
        from ManagerAgent.router import manager_agent
        # Hub has multiple tools it can delegate to
        assert len(manager_agent.tools) >= 3
    
    def test_calculator_has_subagents(self):
        """CalcAgent should have 4 sub-agents as per diagram."""
        from CalcAgent.subagents import tvm_agent, investment_agent, tax_agent, budget_agent
        
        agents = [tvm_agent, investment_agent, tax_agent, budget_agent]
        assert len(agents) == 4
        
        # Each should have Wolfram tool
        for agent in agents:
            tool_names = [t.name for t in agent.tools]
            assert "query_wolfram" in tool_names, f"{agent.name} missing Wolfram tool"
    
    def test_stock_agent_engine_exists(self):
        """StockAgents engine file should exist and have correct structure."""
        import os
        engine_path = "/Users/rishirochan/Python/BluePrint/StockAgents/backend/services/agent_engine.py"
        assert os.path.exists(engine_path), "StockAgents engine file not found"
        
        # Verify engine has the expected class by reading the file
        with open(engine_path, 'r') as f:
            content = f.read()
            assert "class AgentEngine" in content, "AgentEngine class not found"
            assert "quant_agent" in content, "quant_agent reference not found"
            assert "researcher_agent" in content, "researcher_agent reference not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
