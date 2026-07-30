import os
import io
import base64
import requests
import traceback
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
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

# Memoria temporal para el hilo de conversación
chat_history = []

# Generación de voz argentina masculina joven a velocidad natural (+10%)
async def generate_voice_male(text: str) -> str:
    clean_text = text.replace("*", "").replace("#", "").strip()
    if not clean_text:
        return ""
    
    communicate = edge_tts.Communicate(clean_text, "es-AR-TomasNeural", rate="+10%")
    fp = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            fp.write(chunk["data"])
    fp.seek(0)
    return base64.b64encode(fp.read()).decode('utf-8')

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

# Endpoint para reiniciar la conversación
@app.post("/api/reset")
async def reset_chat():
    global chat_history
    chat_history = []
    return {"status": "ok", "message": "Historial reiniciado"}

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    global chat_history
    try:
        if not GROQ_API_KEY:
            return {"response": "Falta la API Key en Render.", "reply": "Falta la API Key en Render."}

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        user_location = data.get("location") or "Benito Juárez, Provincia de Buenos Aires, Argentina"
        
        if not user_text:
            return {"response": "No recibí ningún texto.", "reply": "No recibí ningún texto."}

        # Búsqueda web ultra rápida (1 resultado) para no demorar la respuesta
        context_web = ""
        if tavily_client:
            try:
                search_query = user_text
                if any(w in user_text.lower() for w in ["clima", "temperatura", "tiempo", "grados", "noticias", "dólar"]):
                    search_query = f"{user_text} en {user_location} 2026"

                search_result = tavily_client.search(query=search_query, max_results=1, search_depth="basic")
                results = search_result.get("results", [])
                
                if results:
                    context_web = f"\n\nINFORMACIÓN EN TIEMPO REAL DE LA WEB PARA {user_location.upper()} (AÑO 2026):\n"
                    for res in results:
                        context_web += f"- {res.get('title')}: {res.get('content')}\n"
            except Exception as e:
                print("Aviso búsqueda Tavily:", e)

        # Reglas de personalidad y comportamiento
        system_prompt = (
            f"Sos Nico IA, un asistente virtual argentino joven (18 años), simpático, ágil y educado. "
            f"El usuario te habla desde: {user_location}. Estamos en el año 2026. "
            "Mantené la lógica estricta del diálogo: si el usuario te pregunta si te acordás de algo, respondé afirmando o recordando la información. "
            "NO uses la palabra 'che'. Respondé de forma breve, clara, directa y fluida (máximo 2 o 3 oraciones)."
        )

        messages_payload = [{"role": "system", "content": system_prompt}]
        
        # Mantiene el hilo enviando los últimos 6 mensajes
        for msg in chat_history[-6:]:
            messages_payload.append(msg)

        user_content = user_text
        if context_web:
            user_content += context_web

        messages_payload.append({"role": "user", "content": user_content})

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages_payload,
            "max_tokens": 120,
            "temperature": 0.4
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=8)
        res_json = response.json()

        if response.status_code == 200:
            reply_text = res_json["choices"][0]["message"]["content"]
            
            chat_history.append({"role": "user", "content": user_text})
            chat_history.append({"role": "assistant", "content": reply_text})

            # Generar audio con la voz corregida
            audio_base64 = await generate_voice_male(reply_text)

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
