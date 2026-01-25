from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os
from src.ingestion import process_pdf
from src.config import settings
from pydantic import BaseModel

app = FastAPI(title=settings.PROJECT_NAME)

class QueryRequest(BaseModel):
    query: str

@app.get("/")
async def root():
    return {"message": "Simplified RAG Pipeline is running"}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        result = await process_pdf(temp_path)
        
        # Cleanup
        os.remove(temp_path)
        
        return {"message": result, "filename": file.filename}
        
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_rag(request: QueryRequest):
    try:
        from src.graph import app_graph
        # Invoke the graph
        result = await app_graph.ainvoke({"question": request.query})
        return {"response": result.get("generation", "No response generated")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
