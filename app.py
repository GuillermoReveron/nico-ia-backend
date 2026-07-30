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

# Voz argentina masculina joven
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

# Función robusta en backend para extraer texto de PDF, Word y TXT
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

def create_pdf_bytes(text_content: str) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, 750, "Documento Generado por Nico IA")
    p.line(40, 740, 550, 740)
    
    p.setFont("Helvetica", 10)
    y = 710
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
        user_location = data.get("location") or "Benito Juárez, Provincia de Buenos Aires, Argentina"
        history_from_client = data.get("history") or []
        user_image_b64 = data.get("image") or ""
        file_b64 = data.get("file_b64") or ""
        filename = data.get("filename") or "documento"
        extracted_text_client = data.get("extracted_text") or ""
        
        if not user_text and not user_image_b64 and not file_b64 and not extracted_text_client:
            return {"response": "No recibí ningún texto o archivo.", "reply": "No recibí ningún texto o archivo."}

        # Procesamiento prioritario de documentos en Python
        document_context = ""
        if file_b64:
            extracted = extract_text_from_file_b64(file_b64, filename)
            if extracted:
                document_context = f"\n\nCONTENIDO EXTRAÍDO DEL DOCUMENTO ({filename}):\n{extracted[:5000]}"
        elif extracted_text_client:
            document_context = f"\n\nCONTENIDO DEL DOCUMENTO ({filename}):\n{extracted_text_client[:5000]}"

        context_web = ""
        if tavily_client and user_text:
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

        system_prompt = (
            f"Sos Nico IA, un asistente virtual argentino joven (18 años), simpático, ágil y educado. "
            f"El usuario te habla desde: {user_location}. Estamos en el año 2026. "
            "Mantené la lógica estricta del diálogo. Si informás la temperatura o el clima, usá SIEMPRE grados Celsius (°C), nunca Fahrenheit. "
            "NO uses la palabra 'che'. Si el usuario subió un documento, analizá el texto provisto y hacé el resumen o respuesta correspondiente directamente sin pedir nada adicional."
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
            "max_tokens": 300,
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

            pdf_b64 = ""
            if any(w in user_text.lower() for w in ["pdf", "descargar informe", "generar documento", "resumen en archivo"]):
                pdf_bytes = create_pdf_bytes(reply_text)
                pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            audio_base64 = await generate_voice_male(reply_text)

            return {
                "response": reply_text, 
                "reply": reply_text,
                "audio": audio_base64,
                "pdf": pdf_b64
            }
        else:
            return {"response": "Error en el servidor.", "reply": "Error en el servidor."}

    except Exception as e:
        traceback.print_exc()
        return {"response": "Error interno.", "reply": "Error interno."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
