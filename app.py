import os
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
            return {"response": "No recibí texto.", "reply": "No recibí texto."}

        # Lista de modelos para rotar si uno se queda sin cuota momentánea
        models_to_try = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
        
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
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            res_data = response.json()

            if response.status_code == 200:
                try:
                    reply_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    break
                except KeyError:
                    continue
            elif response.status_code == 429:
                # Si se agota la cuota por minuto, prueba automáticamente el siguiente modelo
                print(f"Cuota saturada en {model_name}, probando el siguiente...")
                continue
            else:
                print(f"Error {response.status_code} en {model_name}:", res_data)

        if not reply_text:
            reply_text = "Che, dame 30 segundos que Google me pausó las respuestas por enviar muy rápido. ¡Volvé a probar en un toque!"

        return {"response": reply_text, "reply": reply_text}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Tuve un contratiempo al procesar la respuesta. Reintentá en un ratito.", "reply": "Tuve un contratiempo al procesar la respuesta. Reintentá en un ratito."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
