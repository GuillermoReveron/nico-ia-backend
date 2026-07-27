import os
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI()

# Configurar API Key de Gemini desde variables de entorno
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Modelo de Gemini listo para producción
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial. Respondés siempre con tono natural de Argentina."
)

class ChatMessage(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(data: ChatMessage):
    try:
        if not GEMINI_API_KEY:
            raise ValueError("No se encontró la GEMINI_API_KEY en las variables de entorno.")
        
        response = model.generate_content(data.message)
        return {"response": response.text}
    except Exception as e:
        print("--- ERROR EN GENERATE_CONTENT ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
