import os
import io
import base64
import requests
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from gtts import gTTS
from tavily import TavilyClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Inicializar cliente de búsqueda Tavily
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        if not GROQ_API_KEY:
            return {"response": "Falta la API Key en Render.", "reply": "Falta la API Key en Render."}

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí ningún texto.", "reply": "No recibí ningún texto."}

        # Búsqueda Web en Tiempo Real con Tavily
        context_web = ""
        if tavily_client:
            try:
                print("--- BÚSQUEDA WEB EN TIEMPO REAL INICIADA ---")
                search_result = tavily_client.search(query=user_text, max_results=3)
                results = search_result.get("results", [])
                
                if results:
                    context_web = "\n\nINFORMACIÓN ACTUALIZADA DE INTERNET EN TIEMPO REAL:\n"
                    for res in results:
                        context_web += f"- {res.get('title')}: {res.get('content')}\n"
            except Exception as e:
                print("Aviso al buscar en Tavily:", e)

        # Construcción del prompt con contexto en vivo
        system_prompt = (
            "Sos Nico IA, un asistente virtual argentino, simpático, cercano y muy servicial. "
            "Tenés acceso a búsquedas en tiempo real en la web. Respondé usando la información más "
            "reciente proporcionada de forma breve, precisa y fluida."
        )

        user_content = user_text
        if context_web:
            user_content += context_web

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        res_json = response.json()

        if response.status_code == 200:
            reply_text = res_json["choices"][0]["message"]["content"]
            
            # Generar audio MP3 de la respuesta
            audio_base64 = ""
            try:
                clean_speech = reply_text.replace("*", "").replace("#", "").strip()
                tts = gTTS(text=clean_speech, lang='es', tld='com.ar')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                audio_base64 = base64.b64encode(fp.read()).decode('utf-8')
            except Exception as e:
                print("Error al generar TTS audio:", e)

            return {
                "response": reply_text, 
                "reply": reply_text,
                "audio": audio_base64
            }
        else:
            return {"response": "Error en el servidor.", "reply": "Error en el servidor."}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Error interno del servidor.", "reply": "Error interno del servidor."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
