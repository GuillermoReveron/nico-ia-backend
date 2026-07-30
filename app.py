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

# Clave proporcionada
NEW_API_KEY = "AQ.Ab8RN6IcHjwlZXbmPEEMnCicqMl3W2QlXghlk-02O5BJsK5CBQ"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", NEW_API_KEY)

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
        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí ningún mensaje de texto.", "reply": "No recibí ningún mensaje de texto."}

        # Selección dinámica de modelo para evitar error 404
        response_text = ""
        model_names = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-flash"]
        
        last_exception = None
        for m_name in model_names:
            try:
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction="Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial."
                )
                res = model.generate_content(user_text)
                response_text = res.text
                break
            except Exception as err:
                last_exception = err
                continue

        if not response_text and last_exception:
            raise last_exception

        return {"response": response_text, "reply": response_text}

    except Exception as e:
        print("--- ERROR EN CHAT ENDPOINT ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
