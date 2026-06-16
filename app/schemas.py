from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None


class AttachmentAction(BaseModel):
    tipo: Literal[
        "enviar_imagem",
        "enviar_documento",
        "criar_rascunho_pedido",
        "chamar_humano",
        "perguntar_dado",
        "nenhuma",
    ]
    arquivo: str | None = None
    legenda: str | None = None
    produto_codigo: str | None = None
    observacao: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    resposta_cliente: str
    intencao: str
    etapa: str
    dados_coletados: dict[str, Any] = Field(default_factory=dict)
    proximas_perguntas: list[str] = Field(default_factory=list)
    acoes: list[AttachmentAction] = Field(default_factory=list)
    precisa_humano: bool = False
    motivo_humano: str | None = None
    debug: dict[str, Any] = Field(default_factory=dict)
