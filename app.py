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
            raise ValueError("No se configuró GEMINI_API_KEY en Render.")

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí texto.", "reply": "No recibí texto."}

        # Modelos válidos en la API v1
        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        
        reply_text = None
        last_error_details = None

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "contents": [{
                    "parts": [{"text": user_text}]
                }],
                "systemInstruction": {
                    "parts": [{"text": "Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial."}]
                }
            }

            headers = {"Content-Type": "application/json"}
            print(f"--- PROBANDO HTTP DIRECTO CON: {model_name} ---")
            
            res = requests.post(url, json=payload, headers=headers, timeout=30)
            res_data = res.json()

            if res.status_code == 200:
                try:
                    reply_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"--- ÉXITO CON: {model_name} ---")
                    break
                except KeyError:
                    continue
            else:
                print(f"Falló {model_name} ({res.status_code}):", res_data)
                last_error_details = res_data

        if not reply_text:
            error_msg = last_error_details.get("error", {}).get("message", "Error al conectar con Gemini") if last_error_details else "No se pudo obtener respuesta."
            raise HTTPException(status_code=500, detail=error_msg)

        return {"response": reply_text, "reply": reply_text}

    except Exception as e:
        print("--- ERROR EN CHAT ENDPOINT ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
