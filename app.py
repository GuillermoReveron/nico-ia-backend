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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        # DIAGNÓSTICO: Imprimir qué clave está leyendo el sistema realmente
        key_preview = f"{GEMINI_API_KEY[:4]}...{GEMINI_API_KEY[-4:]}" if len(GEMINI_API_KEY) > 8 else "CLAVE_INVALIDA_O_VACIA"
        print(f"=== CLAVE LEÍDA POR RENDER: {key_preview} ===")

        if not GEMINI_API_KEY:
            return {"response": "Falta GEMINI_API_KEY en Render.", "reply": "Falta GEMINI_API_KEY en Render."}

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí ningún texto.", "reply": "No recibí ningún texto."}

        # Probamos endpoint REST directo con gemini-2.0-flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": user_text}]}]
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        res_json = response.json()

        print(f"=== STATUS CODE GOOGLE: {response.status_code} ===")

        if response.status_code == 200:
            reply_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            return {"response": reply_text, "reply": reply_text}
        else:
            err_msg = res_json.get("error", {}).get("message", "Error desconocido")
            print(f"=== ERROR CRUDO GOOGLE ===: {err_msg}")
            
            # Si el IP de Render está bloqueado en Gemini, usamos un fallback automático
            return {
                "response": "Google bloqueó la petición por límite de IP/Cuota de Render. Necesitamos cambiar de proveedor o usar proxy.",
                "reply": "Google bloqueó la petición por límite de IP/Cuota de Render. Necesitamos cambiar de proveedor o usar proxy."
            }

    except Exception as e:
        traceback.print_exc()
        return {"response": "Error interno del servidor.", "reply": "Error interno del servidor."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
