from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from services.query_manager import query_manager
from api import deps
from jose import JWTError, jwt
from core.config import settings

router = APIRouter()

@router.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    """
    WebSocket for real-time Agentic Analysis.
    Authentication is a bit tricky with pure WebSockets, usually passed in query param or initial message.
    """
    await websocket.accept()
    
    # Basic Auth check via Query Param ?token=... (Simplified)
    token = websocket.query_params.get("token")
    user_id = "guest"
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
        except:
            await websocket.close(code=1008)
            return

    try:
        while True:
            data = await websocket.receive_text()
            print(f"WS Received raw: {data}")
            
            # Sanitize input: strip quotes if it's a JSON stringified primitive string
            if data.startswith('"') and data.endswith('"'):
                data = data[1:-1]
                
            print(f"WS Processing: {data}")
            
            try:
                # Process query
                response = await query_manager.process_query(data, user_id=user_id)
                print(f"WS sending: {response}")
                await websocket.send_json(response)
            except Exception as e:
                import traceback
                print(f"Error processing query: {e}")
                traceback.print_exc()
                await websocket.send_json({"error": str(e), "recommendation": "I encountered an error processing your request."})
    except WebSocketDisconnect:
        # Handle disconnect
        pass
