import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

# Credenciales
QDRANT_URL = "https://2898acbf-d4f7-4a1d-9547-66f2ea707e9b.us-west-2-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6ZGQyNjcwNjItMGRmOS00ZGI4LWI5YTAtYzc5NTMxMTAzYTUzIn0.6oxv71urQdmGIBbL0HNp_VnSSQdtxZBSGhc4DfNngIo"
GEMINI_API_KEY = "AQ.Ab8RN6LyVcCg-AzM-B0viesDh8srr8TwVk4pq1fxmuOQ0mjzPQ"
COLECCION_NOMBRE = "memoria_nico"

# Clientes
client_gemini = genai.Client(api_key=GEMINI_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

app = FastAPI()

# Permitir solicitudes desde cualquier origen (CORS libre para Android)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def read_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Servidor Nico IA Activo</h1>"

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    try:
        form = await request.form()
        prompt = form.get("prompt", "")

        if not prompt:
            return JSONResponse(content={"response": "Che, no me llegó ningún texto o audio. ¿Me repetís?"})

        contexto_str = ""
        try:
            vector = list(embedding_model.embed([prompt]))[0].tolist()
            resultados = qdrant.query_points(
                collection_name=COLECCION_NOMBRE,
                query=vector,
                limit=3
            ).points
            contextos = [hit.payload["sintesis"] for hit in resultados if "sintesis" in hit.payload]
            contexto_str = "\n---\n".join(contextos) if contextos else ""
        except Exception:
            contexto_str = ""

        system_prompt = (
            "Tu nombre es Nico. Sos una IA autónoma, amigable, clara y profesional. "
            "Hablá siempre en castellano argentino (usá el voseo nativo: 'sos', 'tenés', 'podés', etc.), "
            "en primera persona y de forma directa y concisa."
        )
        if contexto_str:
            system_prompt += f"\n\nContexto de tu memoria web:\n{contexto_str}"

        prompt_final = f"{system_prompt}\n\nPregunta del usuario: {prompt}"

        # Consulta real a Gemini 2.5 Flash
        res_g = client_gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_final
        )

        respuesta_texto = res_g.text.strip()
        return JSONResponse(content={"response": respuesta_texto})

    except Exception as e:
        return JSONResponse(content={"response": f"Tuve un problema al procesar la respuesta: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
