"""CLI entry point for the Financial Calculation Agent."""

import asyncio
from CalcAgent.agent import financial_agent
from CalcAgent.config.utils import run_with_retry


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
    print("Type 'quit', 'exit', or 'bye' to stop.")
    print("=" * 60)
    print()
    
    while True:
        try:
            query = input("You: ").strip()
            
            if not query:
                continue
                
            # Handle exit commands locally so we don't send "bye" to the agent
            if query.lower() in ("quit", "exit", "q", "bye"):
                print("Goodbye!")
                break
            
            print("\nCalculating...\n")
            
            # Use retry logic to handle intermittent tool parsing errors
            result = await run_with_retry(financial_agent, query, max_retries=3)
            print(f"Agent: {result.final_output}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
