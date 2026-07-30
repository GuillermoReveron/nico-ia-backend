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

        # Búsqueda optimizada y rápida en Tavily
        context_web = ""
        if tavily_client:
            try:
                # Si pregunta por el clima o temperatura, forzamos búsqueda meteorológica precisa
                search_query = user_text
                if any(w in user_text.lower() for w in ["clima", "temperatura", "tiempo", "grados"]):
                    search_query = f"clima hoy en Benito Juarez Buenos Aires Argentina temperatura actual"

                search_result = tavily_client.search(query=search_query, max_results=2, search_depth="basic")
                results = search_result.get("results", [])
                
                if results:
                    context_web = "\n\nINFORMACIÓN ACTUALIZADA DE INTERNET:\n"
                    for res in results:
                        context_web += f"- {res.get('title')}: {res.get('content')}\n"
            except Exception as e:
                print("Aviso búsqueda:", e)

        system_prompt = (
            "Sos Nico IA, un asistente virtual argentino, directo y rápido. "
            "Respondé de forma SÚPER BREVE (máximo 2 o 3 oraciones cortas). "
            "Usa la información en tiempo real para dar datos exactos de clima, noticias o fechas."
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
            ],
            "max_tokens": 150,
            "temperature": 0.3
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=8)
        res_json = response.json()

        if response.status_code == 200:
            reply_text = res_json["choices"][0]["message"]["content"]
            
            audio_base64 = ""
            try:
                clean_speech = reply_text.replace("*", "").replace("#", "").strip()
                tts = gTTS(text=clean_speech, lang='es', tld='com.ar')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                audio_base64 = base64.b64encode(fp.read()).decode('utf-8')
            except Exception as e:
                print("Error TTS:", e)

            return {
                "response": reply_text, 
                "reply": reply_text,
                "audio": audio_base64
            }
        else:
            return {"response": "Error en el servidor.", "reply": "Error en el servidor."}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Error interno.", "reply": "Error interno."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
