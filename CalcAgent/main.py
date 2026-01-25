"""CLI entry point for the Financial Calculation Agent."""

import asyncio
from agents import Runner
from CalcAgent.agent import orchestrator


async def main():
    """Interactive CLI for testing the agent system."""
    print("=" * 60)
    print("Financial Calculation Agent")
    print("=" * 60)
    print("Ask me about:")
    print("  • Future/present value calculations")
    print("  • Loan payments and mortgages")
    print("  • Compound interest and ROI")
    print("  • Federal tax estimates")
    print("  • Savings projections")
    print()
    print("Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    print()
    
    while True:
        try:
            query = input("You: ").strip()
            
            if not query:
                continue
                
            if query.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            
            print("\nCalculating...\n")
            
            result = await Runner.run(orchestrator, query)
            print(f"Agent: {result.final_output}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
