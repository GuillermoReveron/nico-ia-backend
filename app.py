import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI()

# Configurar la API Key desde la variable de entorno
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Usar un nombre de modelo soportado
model = genai.GenerativeModel("gemini-1.5-flash")

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        response = model.generate_content(request.message)
        return {"response": response.text}
    except Exception as e:
        print(f"Error en Gemini: {str(e)}")  # Esto sí lo imprimirá en los logs
        raise HTTPException(status_code=500, detail=str(e))
