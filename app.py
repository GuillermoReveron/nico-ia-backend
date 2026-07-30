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
            raise ValueError("No se encontró la GEMINI_API_KEY en Render.")

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí ningún mensaje de texto.", "reply": "No recibí ningún mensaje de texto."}

        # Intentar llamada con parámetro ?key= primero, y si es token con Authorization Header
        url_with_key = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [{"text": user_text}]
            }],
            "systemInstruction": {
                "parts": [{"text": "Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial."}]
            }
        }

        # Probar envío con autenticación por Header (para tokens AQ...) y fallback por Query Param
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GEMINI_API_KEY}"
        }

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
            json=payload,
            headers=headers,
            timeout=30
        )

        # Si no acepta Bearer Token, probamos por Query Parameter sin Bearer
        if response.status_code == 401:
            response = requests.post(
                url_with_key,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

        res_data = response.json()

        if response.status_code != 200:
            print("--- ERROR GOOGLE API RESPONSE ---", res_data)
            error_msg = res_data.get("error", {}).get("message", "Error en la API de Google")
            raise HTTPException(status_code=response.status_code, detail=error_msg)

        reply_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
        return {"response": reply_text, "reply": reply_text}

    except Exception as e:
        print("--- ERROR EN CHAT ENDPOINT ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
