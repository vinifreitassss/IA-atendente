from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.ai_client import AtendimentoAI
from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse
from app.storage import Storage
from app.tools import LocalTools

settings = get_settings()
storage = Storage()
tools = LocalTools()
ai = AtendimentoAI(storage=storage, tools=tools)

app = FastAPI(
    title="IA Atendente",
    version="0.0.1-alpha",
    description="Motor local de conversação e ações para atendimento comercial.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": "0.0.1-alpha",
        "openai_configurada": bool(settings.openai_api_key),
        "modelo": settings.openai_model,
    }


@app.get("/api/contexto")
def contexto() -> dict:
    return {
        "empresa": len(tools.empresa()),
        "produtos": len(tools.produtos()),
        "objecoes": len(tools.objecoes()),
        "scripts": len(tools.scripts()),
        "campos_pedido": len(tools.campos_pedido()),
        "catalogos": len(tools.catalogos()),
    }


@app.get("/api/produtos")
def produtos() -> list[dict[str, str]]:
    return tools.produtos()


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")

    conversation_id = storage.ensure_conversation(payload.conversation_id)
    storage.add_message(conversation_id, "user", message)
    return ai.responder(conversation_id, message)


# Arquivos estáticos e mídia local.
# Os CSVs podem referenciar caminhos como midia/produtos/TROF-001/foto1.jpg
# ou catalogos/catalogo_trofeus.pdf.
app.mount("/midia", StaticFiles(directory=settings.media_dir), name="midia")
app.mount("/catalogos", StaticFiles(directory=settings.catalog_dir), name="catalogos")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
