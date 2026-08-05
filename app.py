import os
import io
import base64
import requests
import urllib.parse
import traceback
import asyncio
import re
import random
from datetime import datetime
import zoneinfo
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
from tavily import TavilyClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

import pypdf
import docx

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

# Voz argentina masculina joven (+10% velocidad)
async def generate_voice_male(text: str) -> str:
    clean_text = text.replace("*", "").replace("#", "").replace("!", "").strip()
    if not clean_text:
        return ""
    
    communicate = edge_tts.Communicate(clean_text, "es-AR-TomasNeural", rate="+10%")
    fp = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            fp.write(chunk["data"])
    fp.seek(0)
    return base64.b64encode(fp.read()).decode('utf-8')

# Generación de imágenes con motor Pollinations.ai
def generate_image_engine(prompt: str) -> str:
    clean_prompt = prompt.lower()
    for word in ["generar", "generame", "crear", "creame", "dibujar", "dibujame", "haceme", "editar", "editame", "cambiar", "cambiame", "una", "un", "imagen", "foto", "de", "del", "la", "el"]:
        clean_prompt = re.sub(rf'\b{word}\b', '', clean_prompt)
    clean_prompt = clean_prompt.strip()
    if not clean_prompt:
        clean_prompt = prompt

    seed = random.randint(1, 99999)
    encoded = urllib.parse.quote(clean_prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true&seed={seed}"

# Extracción de texto de documentos (PDF, DOCX, TXT)
def extract_text_from_file_b64(file_b64: str, filename: str) -> str:
    try:
        if "," in file_b64:
            file_b64 = file_b64.split(",")[1]
            
        file_bytes = base64.b64decode(file_b64)
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        extracted_text = ""

        if ext == "pdf":
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    extracted_text += txt + "\n"
                
        elif ext in ["doc", "docx"]:
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                if para.text:
                    extracted_text += para.text + "\n"
                
        else:
            extracted_text = file_bytes.decode('utf-8', errors='ignore')

        return extracted_text.strip()
    except Exception as e:
        print("Error extrayendo texto del documento:", e)
        traceback.print_exc()
        return ""

# BÚSQUEDA METEOROLÓGICA INTELIGENTE EN TIEMPO REAL VÍA TAVILY
def get_weather_exact(user_text: str, default_location: str) -> str:
    try:
        match = re.search(r'\b(?:en|de|para)\s+(.+)', user_text, re.IGNORECASE)
        city_query = match.group(1).strip().replace("?", "").replace("¿", "").replace(".", "") if match else default_location.split(",")[0]

        time_target = "actual hoy ahora" if any(w in user_text.lower() for w in ["actual", "ahora", "hoy", "momento"]) else "mañana pronostico"

        if tavily_client:
            search_query = f"clima temperatura {time_target} {city_query} Servicio Meteorologico Nacional Argentina"
            search_result = tavily_client.search(query=search_query, max_results=2, search_depth="basic")
            results = search_result.get("results", [])
            
            if results:
                context_clima = f"DATOS REALES DEL TIEMPO OBTENIDOS EN TIEMPO REAL PARA {city_query.upper()}:\n"
                for res in results:
                    title = res.get('title', '')
                    content = res.get('content', '')
                    context_clima += f"- {title}: {content}\n"
                return context_clima
    except Exception as e:
        print("Aviso: Error o demora en Tavily al consultar clima:", e)
    return ""

# Creador de PDF con formato limpio de paginado
def create_pdf_binary(text_content: str) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, 750, "Resumen e Informe - Nico IA")
    p.line(40, 740, 550, 740)
    
    p.setFont("Helvetica", 10)
    y = 710
    clean_lines = text_content.replace("#", "").replace("*", "").split('\n')
    
    for line in clean_lines:
        while len(line) > 80:
            p.drawString(40, y, line[:80])
            line = line[80:]
            y -= 15
            if y < 40:
                p.showPage()
                y = 750
        p.drawString(40, y, line)
        y -= 15
        if y < 40:
            p.showPage()
            y = 750
            
    p.save()
    buffer.seek(0)
    return buffer.getvalue()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "<h1>Servidor Nico IA activo</h1>"

# ENDPOINT DE DESCARGA DIRECTA DE PDF
@app.post("/api/download-pdf")
async def download_pdf_endpoint(request: Request):
    try:
        data = await request.json()
        content = data.get("content") or "Sin contenido."
        pdf_bytes = create_pdf_binary(content)
        
        headers = {
            'Content-Disposition': 'attachment; filename="Informe_Resumen_Nico_IA.pdf"'
        }
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except Exception as e:
        print("Error descargando PDF:", e)
        return Response(content=b"Error generando PDF", status_code=500)

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        if not GROQ_API_KEY:
            return {"response": "Falta la API Key en Render.", "reply": "Falta la API Key en Render."}

        data = await request.json()
        user_text = data.get("message") or data.get("prompt") or data.get("text") or ""
        user_location = data.get("location") or "Benito Juárez, Provincia de Buenos Aires, Argentina"
        history_from_client = data.get("history") or []
        user_image_b64 = data.get("image") or ""
        file_b64 = data.get("file_b64") or ""
        filename = data.get("filename") or "documento"
        
        if not user_text and not user_image_b64 and not file_b64:
            return {"response": "No recibí ningún texto o archivo.", "reply": "No recibí ningún texto o archivo."}

        # HORA ACTUAL ARGENTINA
        tz_arg = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
        now_arg = datetime.now(tz_arg)
        current_time_str = now_arg.strftime("%H:%M hs del %d/%m/%Y")

        # 1. CORTESÍAS
        clean_user = user_text.lower().strip().replace(".", "").replace(",", "").replace("!", "")
        polite_negatives = ["no", "no gracias", "no no gracias", "gracias", "listo", "chau", "nada mas", "no nada mas", "gracias nico"]
        
        if clean_user in polite_negatives:
            reply_text = "¡De nada! Cualquier otra cosa que necesites, decime."
            audio_base64 = await generate_voice_male(reply_text)
            return {"response": reply_text, "reply": reply_text, "audio": audio_base64}

        # 2. GENERACIÓN DE IMÁGENES
        image_triggers = [
            r"generar.*imagen", r"crear.*imagen", r"hacer.*imagen", r"haceme.*imagen",
            r"generar.*foto", r"crear.*foto", r"hacer.*foto", r"haceme.*foto",
            r"dibujar", r"dibujame", r"hazme.*dibujo", r"graficame", r"haz.*un.*dibujo",
            r"imagen de", r"foto de", r"dibujo de"
        ]
        
        is_image_request = any(re.search(pattern, user_text.lower()) for pattern in image_triggers)

        if is_image_request:
            img_url = generate_image_engine(user_text)
            reply_text = f"¡De una! Acá tenés la imagen lista:\n\n![Imagen Generada]({img_url})"
            audio_base64 = await generate_voice_male("¡De una! Acá te generé la imagen que me pediste.")
            return {
                "response": reply_text,
                "reply": reply_text,
                "audio": audio_base64
            }

        # 3. EXTRAER DOCUMENTOS
        document_context = ""
        if file_b64:
            extracted = extract_text_from_file_b64(file_b64, filename)
            if extracted:
                document_context = f"\n\nCONTENIDO EXTRAÍDO DEL DOCUMENTO ({filename}):\n{extracted[:6000]}"

        # 4. CLIMA O INFORMACIÓN WEB
        context_web = ""
        weather_triggers = ["clima", "temperatura", "tiempo", "grados", "llueve", "lluvia", "pronóstico", "pronostico", "mañana", "hoy"]
        is_weather = any(w in user_text.lower() for w in weather_triggers)

        if is_weather:
            exact_weather = get_weather_exact(user_text, user_location)
            if exact_weather:
                context_web = f"\n\n{exact_weather}\n"

        if not context_web and tavily_client and len(user_text.strip()) > 3:
            try:
                search_query = f"{user_text} 2026"
                search_result = tavily_client.search(query=search_query, max_results=1, search_depth="basic")
                results = search_result.get("results", [])
                if results:
                    context_web = f"\n\nINFORMACIÓN EN TIEMPO REAL DE LA WEB:\n"
                    for res in results:
                        context_web += f"- {res.get('title', '')}: {res.get('content', '')}\n"
            except Exception as e:
                print("Aviso búsqueda Tavily:", e)

        # 5. MODELO PRINCIPAL (Llama 3.3 70B)
        system_prompt = (
            f"Sos Nico IA, un asistente virtual argentino joven (18 años), simpático, ágil y educado. "
            f"La fecha y hora exacta actual en Argentina es: {current_time_str}. "
            "REGLA CRÍTICA DE MEMORIA: Leé ATENTAMENTE TODO el historial de la conversación desde el primer mensaje hasta el último. "
            "Debes recordar y tener siempre presentes todos los datos personales mencionados en el historial (por ejemplo, nombres de usuario, familiares como hijos, preferencias, etc.) sin importar cuántos mensajes hayan pasado. "
            "Si en el prompt recibís datos del clima de una ciudad, responde con los datos meteorológicos exactos de los resultados web. "
            "Respondé ÚNICAMENTE sobre la ciudad consultada. "
            "Si el usuario te pide un resumen de un documento o texto, explicáselo detalladamente en puntos clave. "
            "Si pide PDF o resumen de estudio, confirmale que se lo dejaste listo para descargar con el botón inferior. NO usás la palabra 'che'."
        )

        messages_payload = [{"role": "system", "content": system_prompt}]
        
        # SIN LÍMITE: Enviamos la totalidad del historial recibido de la sesión actual
        for msg in history_from_client:
            messages_payload.append(msg)

        user_content = user_text
        if document_context:
            user_content += document_context
        if context_web:
            user_content += context_web
        if user_image_b64:
            user_content += "\n[IMAGEN/VIDEO ADJUNTADO POR EL USUARIO]"

        messages_payload.append({"role": "user", "content": user_content})

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages_payload,
            "max_tokens": 600,
            "temperature": 0.3
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            res_json = response.json()
            reply_text = res_json["choices"][0]["message"]["content"]

            has_pdf = False
            pdf_triggers = ["pdf", "descargar", "informe", "documento", "estudiar", "resumen", "resumir"]
            if any(w in user_text.lower() for w in pdf_triggers) or file_b64:
                has_pdf = True

            audio_base64 = await generate_voice_male(reply_text)

            return {
                "response": reply_text, 
                "reply": reply_text,
                "audio": audio_base64,
                "has_pdf": has_pdf
            }
        else:
            print("Error respuesta Groq:", response.status_code, response.text)
            return {"response": "Superé el límite de consultas por este momento. Probá en un ratito.", "reply": "Superé el límite de consultas por este momento. Probá en un ratito."}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Error interno del servidor.", "reply": "Error interno del servidor."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
