import asyncio
import os
from groq import AsyncGroq
from dotenv import load_dotenv

# Load env vars from .env
load_dotenv()

async def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    print(f"DEBUG: API Key found: {'Yes' if api_key else 'No'}")
    if api_key:
        print(f"DEBUG: Key starts with: {api_key[:4]}...")
    
    try:
        client = AsyncGroq(api_key=api_key)
        print("DEBUG: Client initialized. Attempting request...")
        
        completion = await client.chat.completions.create(
            messages=[
                {"role": "user", "content": "Explain quantum computing in one sentence."}
            ],
            model="llama-3.3-70b-versatile",
        )
        print("DEBUG: Success!")
        print(f"Response: {completion.choices[0].message.content}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_groq())
