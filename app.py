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

        # Modelos de respaldo
        target_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-latest"]
        
        selected_model_name = None
        try:
            # Obtener modelos disponibles y limpiar el prefijo 'models/'
            available_models = [m.name.replace("models/", "") for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
            if available_models:
                for tm in target_models:
                    matching = [m for m in available_models if tm in m]
                    if matching:
                        selected_model_name = matching[0]
                        break
                if not selected_model_name:
                    selected_model_name = available_models[0]
        except Exception as e:
            print("No se pudo listar modelos, usando default:", e)
            selected_model_name = "gemini-2.5-flash"

        print(f"--- USANDO MODELO LIMPIO: {selected_model_name} ---")

        model = genai.GenerativeModel(
            model_name=selected_model_name,
            system_instruction="Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial."
        )
        
        response = model.generate_content(user_text)
        return {"response": response.text, "reply": response.text}

    except Exception as e:
        print("--- ERROR EN CHAT ENDPOINT ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
