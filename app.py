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

        # Lista de modelos estables garantizados
        candidate_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]
        
        response_text = None
        last_error = None

        for m_name in candidate_models:
            try:
                print(f"--- PROBANDO MODELO: {m_name} ---")
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction="Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial."
                )
                res = model.generate_content(user_text)
                if res and res.text:
                    response_text = res.text
                    print(f"--- ÉXITO CON MODELO: {m_name} ---")
                    break
            except Exception as err:
                print(f"Falló {m_name}: {err}")
                last_error = err
                continue

        if not response_text:
            if last_error:
                raise last_error
            raise RuntimeError("Ningún modelo de Gemini pudo procesar la solicitud.")

        return {"response": response_text, "reply": response_text}

    except Exception as e:
        print("--- DETALLE DEL ERROR REAL ---")
        traceback.print_exc()
        # Devolver el error exacto en el JSON para no andar a ciegas
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
