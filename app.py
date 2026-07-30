import os
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inicializar cliente de Google GenAI
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print("Error inicializando cliente GenAI:", e)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        if not GEMINI_API_KEY or not client:
            return {"response": "Falta GEMINI_API_KEY en Render.", "reply": "Falta GEMINI_API_KEY en Render."}

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí ningún texto.", "reply": "No recibí ningún texto."}

        # Modelos oficial y de respaldo gestionados por la SDK
        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
        reply_text = None

        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_text,
                    config={
                        "system_instruction": "Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial."
                    }
                )
                if response and response.text:
                    reply_text = response.text
                    print(f"--- RESPUESTA EXITOSA CON: {model_name} ---")
                    break
            except Exception as mod_err:
                print(f"--- AVISO EN {model_name} ---:", mod_err)

        if not reply_text:
            reply_text = "¡Hola che! Los servidores de Google están saturados en este momento. Aguardame un ratito y volvé a probar."

        return {"response": reply_text, "reply": reply_text}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Inconveniente temporal. Intentá nuevamente en unos minutos.", "reply": "Inconveniente temporal. Intentá nuevamente en unos minutos."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
