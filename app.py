import os
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        if not GEMINI_API_KEY:
            raise ValueError("No se configuró GEMINI_API_KEY en Render.")

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí texto.", "reply": "No recibí texto."}

        # Usamos el modelo v1 actual compatible
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        response = model.generate_content(
            user_text,
            generation_config={"temperature": 0.7}
        )
        
        return {"response": response.text, "reply": response.text}

    except Exception as e:
        print("--- ERROR EN CHAT ENDPOINT ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
