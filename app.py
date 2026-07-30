import os
import io
import base64
import requests
import urllib.parse
import traceback
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
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

# Configuración de Claves (Groq o Gemini) y Tavily
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

# --- FUNCIONES DE AUDIO Y GENERACIÓN ---

# Generación de voz argentina masculina joven
async def generate_voice_male(text: str) -> str:
    # Limpiar texto de formatos antes de leer
    clean_text = text.replace("*", "").replace("#", "").strip()
    if not clean_text:
        return ""
    
    # Tomas es voz argentina, rate +10% la hace más ágil
    communicate = edge_tts.Communicate(clean_text, "es-AR-TomasNeural", rate="+10%")
    fp = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            fp.write(chunk["data"])
    fp.seek(0)
    # Devolver audio en Base64 para el navegador
    return base64.b64encode(fp.read()).decode('utf-8')

# Generación de imágenes 100% GRATIS con Pollinations.ai
def generate_free_image_url(prompt: str) -> str:
    clean_prompt = urllib.parse.quote(prompt.strip())
    # Genera imagen de 1024x1024 sin logo, rápido y gratis
    return f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true"

# Extracción robusta de texto de documentos (PDF, Word, TXT)
def extract_text_from_file_b64(file_b64: str, filename: str) -> str:
    try:
        # Remover cabecera si existe
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

# Helper para generar archivo PDF descargable si el usuario lo pide
def create_pdf_bytes(text_content: str) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, 750, "Documento Generado por Nico IA")
    p.line(40, 740, 550, 740)
    
    p.setFont("Helvetica", 10)
    y = 710
    # Envolver texto simple para que entre en la página
    for line in text_content.split('\n'):
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

# --- RUTAS DE LA API ---

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
        # Ubicación predeterminada si el navegador no envía GPS
        user_location = data.get("location") or "Benito Juárez, Provincia de Buenos Aires, Argentina"
        history_from_client = data.get("history") or []
        user_image_b64 = data.get("image") or ""
        file_b64 = data.get("file_b64") or ""
        filename = data.get("filename") or "documento"
        
        if not user_text and not user_image_b64 and not file_b64:
            return {"response": "No recibí ningún texto o archivo.", "reply": "No recibí ningún texto o archivo."}

        # 1. DETECTAR PEDIDO DE IMAGEN ( Pollinations Gratuito )
        image_keywords = ["generar imagen", "crear imagen", "dibujar", "haceme una foto de", "crear foto de", "dibujame"]
        is_image_request = any(kw in user_text.lower() for kw in image_keywords)

        if is_image_request:
            img_url = generate_free_image_url(user_text)
            reply_text = f"¡De una! Acá tenés la imagen que me pediste:\n\n![Imagen Generada]({img_url})"
            # El audio solo confirma, no describe la imagen.
            audio_base64 = await generate_voice_male("¡De una! Acá te generé la imagen que me pediste.")
            return {
                "response": reply_text,
                "reply": reply_text,
                "audio": audio_base64
            }

        # 2. PROCESAR DOCUMENTOS ( PDF, Word )
        document_context = ""
        if file_b64:
            extracted = extract_text_from_file_b64(file_b64, filename)
            if extracted:
                # Limitamos a 5000 caracteres para no saturar el prompt
                document_context = f"\n\nCONTENIDO EXTRAÍDO DEL DOCUMENTO ({filename}):\n{extracted[:5000]}"

        # 3. BÚSQUEDA WEB INTELIGENTE (Tavily)
        # Solo busca si hay palabras clave meteorológicas o de info en tiempo real.
        context_web = ""
        # Se agregaron 'mañana' y 'grados' para capturar la pregunta "¿Qué temperatura hará mañana?"
        search_triggers = ["clima", "temperatura", "tiempo", "grados", "noticias", "dólar", "cotización", "precio", "mañana", "hoy"]
        
        # Filtro preventivo: NO buscar si es una frase corta de cortesía
        # (Soluciona el error de "no, gracias" contestando foros)
        polite_phrases = ["gracias", "no gracias", "chau", "listo", "anotado"]
        is_polite_reply = any(p == user_text.lower().strip() for p in polite_phrases)
        
        should_search_web = any(w in user_text.lower() for w in search_triggers) and not is_polite_reply

        if tavily_client and should_search_web:
            try:
                # Forzar búsqueda en la ubicación y año correcto
                search_query = f"{user_text} en {user_location} 2026"
                search_result = tavily_client.search(query=search_query, max_results=1, search_depth="basic")
                results = search_result.get("results", [])
                
                if results:
                    context_web = f"\n\nINFORMACIÓN EN TIEMPO REAL DE LA WEB PARA {user_location.upper()} (AÑO 2026):\n"
                    for res in results:
                        context_web += f"- {res.get('title')}: {res.get('content')}\n"
            except Exception as e:
                print("Aviso búsqueda Tavily:", e)

        # 4. CONSTRUIR EL PROMPT PARA LA IA (Llama 3.3)
        system_prompt = (
            f"Sos Nico IA, un asistente virtual argentino joven (18 años), simpático, ágil y educado. "
            f"El usuario te habla desde: {user_location}. Estamos en el año 2026. "
            "Mantené la lógica estricta del diálogo. Si el usuario te responde amablemente (ej: 'gracias'), contestá breve y cordial sin buscar info. "
            "Si informás la temperatura o el clima, usá SIEMPRE grados Celsius (°C), nunca Fahrenheit. "
            "NO uses la palabra 'che'. Si el usuario subió un documento, analizalo directamente. "
            "Si el usuario pide generar un informe en PDF, confirmale que se lo dejaste listo para descargar."
        )

        messages_payload = [{"role": "system", "content": system_prompt}]
        
        # Mantener historial reciente (últimos 3 intercambios)
        for msg in history_from_client[-6:]:
            messages_payload.append(msg)

        # Inyectar contextos al mensaje del usuario
        user_content = user_text
        if document_context:
            user_content += document_context
        if context_web:
            user_content += context_web
        if user_image_b64:
            # Llama no ve la imagen, pero sabe que está ahí.
            user_content += "\n[IMAGEN/VIDEO ADJUNTADO POR EL USUARIO]"

        messages_payload.append({"role": "user", "content": user_content})

        # 5. LLAMADA A LA API DE GROQ (Llama 3.3 70B)
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages_payload,
            "max_tokens": 300, # Respuestas ágiles
            "temperature": 0.4 # Un poco de creatividad pero controlado
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        # Tiempo de espera un poco más largo por si Tavily tarda
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        res_json = response.json()

        if response.status_code == 200:
            reply_text = res_json["choices"][0]["message"]["content"]

            # 6. VERIFICAR SI PIDIÓ GENERAR UN PDF DESCARGABLE
            pdf_b64 = ""
            if any(w in user_text.lower() for w in ["pdf", "descargar informe", "generar documento", "resumen en archivo"]):
                # Crear PDF con la respuesta de la IA
                pdf_bytes = create_pdf_bytes(reply_text)
                pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # Generar audio de la respuesta
            audio_base64 = await generate_voice_male(reply_text)

            return {
                "response": reply_text, 
                "reply": reply_text,
                "audio": audio_base64,
                "pdf": pdf_b64 # Vacío si no se solicitó
            }
        else:
            print("Error Groq API:", res_json)
            return {"response": "Error en el servidor.", "reply": "Error en el servidor."}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Error interno.", "reply": "Error interno."}

# Punto de entrada para Render / Uvicorn
if __name__ == "__main__":
    import uvicorn
    # Render usa la variable PORT
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
