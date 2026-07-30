import os
import requests
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        if not GEMINI_API_KEY:
            return {"response": "Falta GEMINI_API_KEY en Render.", "reply": "Falta GEMINI_API_KEY en Render."}

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí texto.", "reply": "No recibí texto."}

        # Usamos gemini-1.5-flash y gemini-2.0-flash como respaldo con endpoint directo
        models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash"]
        reply_text = None

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "contents": [{
                    "parts": [{"text": user_text}]
                }],
                "systemInstruction": {
                    "parts": [{"text": "Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial."}]
                }
            }

            headers = {"Content-Type": "application/json"}
            
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                res_data = response.json()

                if response.status_code == 200:
                    reply_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"--- RESPUESTA EXITOSA DE: {model_name} ---")
                    break
                else:
                    print(f"--- AVISO {model_name} ({response.status_code}) ---:", res_data.get("error", {}).get("message", "Sin detalle"))
            except Exception as req_err:
                print(f"Error consultando {model_name}: {req_err}")

        if not reply_text:
            reply_text = "¡Hola che! Google tiene los servidores con límite de velocidad de respuestas por un momento. Probá escribirme de nuevo en un ratito."

        return {"response": reply_text, "reply": reply_text}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Ocurrió un inconveniente temporal. Intentá nuevamente.", "reply": "Ocurrió un inconveniente temporal. Intentá nuevamente."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
