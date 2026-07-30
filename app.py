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

# Memoria temporal simple para mantener el hilo del chat
chat_history = []

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    global chat_history
    try:
        if not GROQ_API_KEY:
            return {"response": "Falta la API Key en Render.", "reply": "Falta la API Key en Render."}

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        
        if not user_text:
            return {"response": "No recibí ningún texto.", "reply": "No recibí ningún texto."}

        # Búsqueda web optimizada con contexto temporal (Año 2026)
        context_web = ""
        if tavily_client:
            try:
                search_query = f"{user_text} 2026"
                search_result = tavily_client.search(query=search_query, max_results=3, search_depth="basic")
                results = search_result.get("results", [])
                
                if results:
                    context_web = "\n\nINFORMACIÓN ACTUALIZADA DE LA WEB (AÑO 2026):\n"
                    for res in results:
                        context_web += f"- {res.get('title')}: {res.get('content')}\n"
            except Exception as e:
                print("Aviso búsqueda Tavily:", e)

        system_prompt = (
            "Sos Nico IA, un asistente virtual argentino, fluido, inteligente y cercano. "
            "Estamos en el año 2026. Mantené el hilo de la conversación recordando los mensajes anteriores. "
            "Respondé de forma concisa, clara y directa, utilizando la información web provista para datos actuales."
        )

        # Armar el paquete de mensajes incluyendo el historial
        messages_payload = [{"role": "system", "content": system_prompt}]
        
        # Agregar los últimos 6 mensajes del historial para no saturar memoria
        for msg in chat_history[-6:]:
            messages_payload.append(msg)

        # Mensaje actual del usuario
        user_content = user_text
        if context_web:
            user_content += context_web

        messages_payload.append({"role": "user", "content": user_content})

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages_payload,
            "max_tokens": 250,
            "temperature": 0.4
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        res_json = response.json()

        if response.status_code == 200:
            reply_text = res_json["choices"][0]["message"]["content"]
            
            # Guardar en el historial la interacción actual
            chat_history.append({"role": "user", "content": user_text})
            chat_history.append({"role": "assistant", "content": reply_text})

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
