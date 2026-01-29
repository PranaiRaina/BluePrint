
import asyncio
import time
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from ManagerAgent.orchestrator import orchestrate_stream
from ManagerAgent.router_intelligence import IntentType

async def verify_streaming():
    print("Starting Streaming Verification...")
    
    # Test Query: Compare
    query = "compare apple and nvidia" 
    
    # Dynamically classify to mimic real behavior
    from ManagerAgent.router_intelligence import classify_intent
    print("Classifying intent...")
    decision = await classify_intent(query)
    intents = decision.intents
    
    start_time = time.time()
    
    print(f"\nQUERY: {query}")
    print(f"INTENTS: {intents}")
    print("-" * 50)
    
    first_token_time = None
    token_count = 0
    
    try:
        async for chunk in orchestrate_stream(query, intents):
            elapsed = time.time() - start_time
            
            if chunk["type"] == "status":
                print(f"[{elapsed:.2f}s] STATUS: {chunk['content']}")
            elif chunk["type"] == "token":
                if first_token_time is None:
                    first_token_time = elapsed
                    print(f"[{elapsed:.2f}s] FIRST TOKEN: {repr(chunk['content'])}")
                
                # Print content to check quality
                sys.stdout.write(chunk['content'])
                sys.stdout.flush()
                token_count += 1
                
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "-" * 50)
    print(f"Total Tokens: {token_count}")
    print(f"First Token Latency: {first_token_time if first_token_time else 'N/A'}")
    print(f"Total Duration: {time.time() - start_time:.2f}s")
    
    if first_token_time and first_token_time < 2.0:
        print("\nSUCCESS: First token received quickly (likely before full completion).")
    else:
        print("\nWARNING: Latency might be high, check if it's truly streaming.")

if __name__ == "__main__":
    asyncio.run(verify_streaming())
