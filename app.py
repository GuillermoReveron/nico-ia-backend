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
            
            # Intento 1 directo
            response = requests.post(url, json=payload, headers=headers, timeout=25)
            res_data = response.json()

            if response.status_code == 200:
                try:
                    reply_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"--- ÉXITO CON: {model_name} ---")
                    break
                except KeyError:
                    pass
            elif response.status_code == 429:
                print(f"Cuota agotada en {model_name}. Esperando 10s para liberar el canal...")
                time.sleep(10)
                # Reintento tras la pausa
                res_retry = requests.post(url, json=payload, headers=headers, timeout=25)
                retry_data = res_retry.json()
                if res_retry.status_code == 200:
                    try:
                        reply_text = retry_data["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"--- ÉXITO TRAS ESPERA CON: {model_name} ---")
                        break
                    except KeyError:
                        pass

        if not reply_text:
            reply_text = "¡Che, bancame unos 20 segundos! Google me frenó un toque por enviar mensajes muy seguidos. Volvé a probar en un momento."

        return {"response": reply_text, "reply": reply_text}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Tuve un contratiempo temporal. Reintentá en un ratito.", "reply": "Tuve un contratiempo temporal. Reintentá en un ratito."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
