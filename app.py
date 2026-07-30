import os
import time
import requests
import traceback
from fastapi import FastAPI, HTTPException, Request
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
            return {"response": "No recibí ningún texto.", "reply": "No recibí ningún texto."}

        # Modelos oficial y secundario habilitados en Gemini API v1beta
        models_to_try = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
        
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
            
            # Reintento si la API devuelve 429 por límite por minuto
            for attempt in range(2):
                response = requests.post(url, json=payload, headers=headers, timeout=25)
                res_data = response.json()

                if response.status_code == 200:
                    try:
                        reply_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"--- ÉXITO CON: {model_name} ---")
                        break
                    except KeyError:
                        break
                elif response.status_code == 429:
                    print(f"Cuota temporal excedida en {model_name}. Esperando 3s... (Intento {attempt + 1})")
                    time.sleep(3)
                else:
                    print(f"Error {response.status_code} en {model_name}:", res_data)
                    break

            if reply_text:
                break

        if not reply_text:
            reply_text = "¡Hola che! Google pausó un momento la respuesta por límite de velocidad. Aguardame unos segundos y volvé a probar."

        return {"response": reply_text, "reply": reply_text}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Tuve un contratiempo. Reintentá en un ratito.", "reply": "Tuve un contratiempo. Reintentá en un ratito."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
