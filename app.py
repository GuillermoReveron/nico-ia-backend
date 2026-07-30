import os
import io
import base64
import requests
import urllib.parse
import traceback
import asyncio
import re
import random
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

# Generar imágenes gratis con Pollinations.ai
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

# Extracción de texto de documentos
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

# DICCIONARIO DIRECTO DE CIUDADES FRECUENTES + BUSCADOR GLOBAL
KNOWN_CITIES = {
    "tres arroyos": (-38.37, -60.27, "Tres Arroyos"),
    "benito juarez": (-37.67, -59.80, "Benito Juárez"),
    "las flores": (-36.01, -59.10, "Las Flores"),
    "la plata": (-34.92, -57.95, "La Plata"),
    "balcarce": (-37.84, -58.25, "Balcarce"),
    "tandil": (-37.32, -59.13, "Tandil"),
    "azul": (-36.77, -59.85, "Azul"),
    "olavarria": (-36.89, -60.32, "Olavarría"),
    "mar del plata": (-38.00, -57.55, "Mar del Plata"),
    "bahia blanca": (-38.71, -62.26, "Bahía Blanca"),
    "necohea": (-38.55, -58.73, "Necochea"),
    "buenos aires": (-34.60, -58.38, "Buenos Aires"),
    "cordoba": (-31.42, -64.18, "Córdoba"),
    "mendoza": (-32.89, -68.84, "Mendoza"),
    "rosario": (-32.95, -60.64, "Rosario")
}

def get_weather_global(user_text: str, default_location: str) -> str:
    try:
        clean_text = user_text.lower().replace("?", "").replace("¿", "").replace(".", "").replace(",", "")
        
        # 1. Verificar si es una ciudad conocida de la región
        lat, lon, city_name = None, None, None
        for city_key, data in KNOWN_CITIES.items():
            if city_key in clean_text:
                lat, lon, city_name = data[0], data[1], data[2]
                break

        # 2. Si no estaba en la lista, buscar en la API global
        if not lat:
            match = re.search(r'\b(?:en|de|para)\s+(.+)', user_text, re.IGNORECASE)
            city_query = match.group(1).strip().replace("?", "").replace("¿", "") if match else default_location.split(",")[0]
            
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city_query)}&count=5&language=es&format=json"
            geo_res = requests.get(geo_url, timeout=5)
            
            if geo_res.status_code == 200 and geo_res.json().get("results"):
                results = geo_res.json()["results"]
                arg_result = next((r for r in results if r.get("country_code") == "AR"), results[0])
                lat = arg_result.get("latitude")
                lon = arg_result.get("longitude")
                city_name = arg_result.get("name", city_query)

        if not lat:
            lat, lon, city_name = -37.67, -59.80, "Benito Juárez"

        # 3. Consultar tiempo real
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto"
        w_res = requests.get(weather_url, timeout=5)
        
        if w_res.status_code == 200:
            daily = w_res.json().get("daily", {})
            max_temp = daily.get("temperature_2m_max", [None, None])[1]
            min_temp = daily.get("temperature_2m_min", [None, None])[1]
            rain = daily.get("precipitation_probability_max", [None, None])[1]
            return f"DATOS METEOROLÓGICOS REALES PARA MAÑANA EN {city_name.upper()}: Máxima {max_temp}°C, Mínima {min_temp}°C, Lluvia {rain}%."
    except Exception as e:
        print("Error en clima global:", e)
    return ""

# Creador de PDF
def create_pdf_binary(text_content: str) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, 750, "Resumen de Estudio - Nico IA")
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

@app.post("/api/download-pdf")
async def download_pdf_endpoint(request: Request):
    try:
        data = await request.json()
        content = data.get("content") or "Sin contenido."
        pdf_bytes = create_pdf_binary(content)
        
        headers = {
            'Content-Disposition': 'attachment; filename="Resumen_Estudio_Nico_IA.pdf"'
        }
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except Exception as e:
        print("Error descargando PDF:", e)
        return {"error": "No se pudo generar el archivo."}

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

        # 4. CLIMA INFALIBLE Y DIRECTO
        context_web = ""
        weather_triggers = ["clima", "temperatura", "tiempo", "grados", "llueve", "lluvia", "pronóstico", "pronostico", "mañana", "hoy"]
        is_weather = any(w in user_text.lower() for w in weather_triggers)

        if is_weather:
            global_weather = get_weather_global(user_text, user_location)
            if global_weather:
                context_web = f"\n\nINFORMACIÓN METEOROLÓGICA EN TIEMPO REAL OBTENIDA:\n{global_weather}\n"

        if not context_web and tavily_client and len(user_text.strip()) > 3:
            try:
                search_query = f"{user_text} 2026"
                search_result = tavily_client.search(query=search_query, max_results=1, search_depth="basic")
                results = search_result.get("results", [])
                if results:
                    context_web = f"\n\nINFORMACIÓN EN TIEMPO REAL DE LA WEB (AÑO 2026):\n"
                    for res in results:
                        context_web += f"- {res.get('title')}: {res.get('content')}\n"
            except Exception as e:
                print("Aviso búsqueda Tavily:", e)

        # 5. MODELO PRINCIPAL (Llama 3.3)
        system_prompt = (
            f"Sos Nico IA, un asistente virtual argentino joven (18 años), simpático, ágil y educado. "
            "Estamos en el año 2026. "
            "Mantené la lógica estricta del diálogo. Respondé ÚNICAMENTE sobre la ciudad consultada por el usuario utilizando los datos del prompt. NUNCA menciones a Benito Juárez a menos que la consulta sea sobre esa ciudad. "
            "Si el usuario te pide un resumen de un documento, explicáselo en puntos clave muy claros. "
            "Si pide PDF o resumen de estudio, confirmale que se lo dejaste listo para descargar. NO usás la palabra 'che'."
        )

        messages_payload = [{"role": "system", "content": system_prompt}]
        
        for msg in history_from_client[-6:]:
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
            "max_tokens": 400,
            "temperature": 0.4
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=12)
        res_json = response.json()

        if response.status_code == 200:
            reply_text = res_json["choices"][0]["message"]["content"]

            has_pdf = False
            pdf_triggers = ["pdf", "descargar", "informe", "documento", "estudiar", "resumen"]
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
            return {"response": "Error en el servidor.", "reply": "Error en el servidor."}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Error interno.", "reply": "Error interno."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
