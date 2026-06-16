import json
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.schemas import AttachmentAction, ChatResponse
from app.storage import Storage
from app.tools import LocalTools


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "resposta_cliente": {"type": "string"},
        "intencao": {"type": "string"},
        "etapa": {"type": "string"},
        "dados_coletados": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "campo": {"type": "string"},
                    "valor": {"type": ["string", "number", "boolean", "null"]},
                },
                "required": ["campo", "valor"],
            },
        },
        "proximas_perguntas": {"type": "array", "items": {"type": "string"}},
        "acoes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": [
                            "enviar_imagem",
                            "enviar_documento",
                            "criar_rascunho_pedido",
                            "chamar_humano",
                            "perguntar_dado",
                            "nenhuma",
                        ],
                    },
                    "arquivo": {"type": ["string", "null"]},
                    "legenda": {"type": ["string", "null"]},
                    "produto_codigo": {"type": ["string", "null"]},
                    "observacao": {"type": ["string", "null"]},
                },
                "required": ["tipo", "arquivo", "legenda", "produto_codigo", "observacao"],
            },
        },
        "precisa_humano": {"type": "boolean"},
        "motivo_humano": {"type": ["string", "null"]},
    },
    "required": [
        "resposta_cliente",
        "intencao",
        "etapa",
        "dados_coletados",
        "proximas_perguntas",
        "acoes",
        "precisa_humano",
        "motivo_humano",
    ],
}


SYSTEM_PROMPT = """
Você é a IA atendente comercial da Silva Campos Esportes, empresa de troféus, medalhas,
placas e personalizados.

Sua função neste alpha:
- atender como vendedora objetiva, simpática e comercial;
- consultar os dados recebidos antes de falar sobre produto, preço, prazo ou catálogo;
- nunca inventar produto, preço, medida, prazo, desconto ou política;
- se faltar dado, pergunte uma coisa por vez;
- se o cliente estiver indeciso, sugira imagens e/ou catálogo;
- se o cliente pedir modelo, imagem, foto, catálogo ou exemplo, gere ações de anexo;
- se houver urgência, desconto, reclamação, pedido fora do padrão ou dúvida fiscal, chame humano;
- colete dados para rascunho de pedido, mas não diga que o pedido está fechado sem confirmação humana;
- no começo de orçamento, priorize: produto, quantidade, tema/personalização, se já tem arte pronta e prazo desejado.

Você deve sempre responder em JSON seguindo o schema. Não escreva nada fora do JSON.

Tipos de ação:
- enviar_imagem: quando fizer sentido mandar foto de produto ou exemplo;
- enviar_documento: quando fizer sentido mandar PDF/catalogo;
- criar_rascunho_pedido: quando houver dados suficientes para rascunho;
- chamar_humano: quando precisar de intervenção humana;
- perguntar_dado: quando a próxima ação é coletar informação;
- nenhuma: quando não há ação.
""".strip()


class AtendimentoAI:
    def __init__(self, storage: Storage | None = None, tools: LocalTools | None = None) -> None:
        self.settings = get_settings()
        self.storage = storage or Storage()
        self.tools = tools or LocalTools()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    def responder(self, conversation_id: str, mensagem: str) -> ChatResponse:
        historico = self.storage.get_recent_messages(conversation_id)
        estado = self.storage.get_state(conversation_id)
        contexto = self.tools.build_context(mensagem)

        if not self.client:
            resposta = self._fallback_sem_api(mensagem, contexto)
        else:
            resposta = self._chamar_openai(mensagem, historico, estado, contexto)

        dados = self._normalizar_resposta(resposta)
        novo_estado = {
            "ultima_intencao": dados["intencao"],
            "etapa": dados["etapa"],
            "dados_coletados": dados["dados_coletados"],
            "precisa_humano": dados["precisa_humano"],
        }
        self.storage.save_state(conversation_id, novo_estado)
        self.storage.add_message(conversation_id, "assistant", dados["resposta_cliente"])

        return ChatResponse(
            conversation_id=conversation_id,
            resposta_cliente=dados["resposta_cliente"],
            intencao=dados["intencao"],
            etapa=dados["etapa"],
            dados_coletados=dados["dados_coletados"],
            proximas_perguntas=dados["proximas_perguntas"],
            acoes=[AttachmentAction(**a) for a in dados["acoes"]],
            precisa_humano=dados["precisa_humano"],
            motivo_humano=dados["motivo_humano"],
            debug={
                "modelo": self.settings.openai_model if self.client else "fallback_sem_api",
                "produtos_consultados": [p.get("codigo") for p in contexto.get("produtos_relevantes", [])],
                "catalogos_consultados": [c.get("codigo") for c in contexto.get("catalogos_relevantes", [])],
            },
        )

    def _erro_humano(self, observacao: str, motivo: str) -> dict[str, Any]:
        return {
            "resposta_cliente": "Tive uma dificuldade interna aqui. Vou chamar uma pessoa da equipe para te ajudar sem te passar informação errada.",
            "intencao": "erro_interno",
            "etapa": "chamar_humano",
            "dados_coletados": [],
            "proximas_perguntas": [],
            "acoes": [
                {
                    "tipo": "chamar_humano",
                    "arquivo": None,
                    "legenda": None,
                    "produto_codigo": None,
                    "observacao": observacao,
                }
            ],
            "precisa_humano": True,
            "motivo_humano": motivo,
        }

    def _chamar_openai(
        self,
        mensagem: str,
        historico: list[dict[str, str]],
        estado: dict[str, Any],
        contexto: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "mensagem_cliente": mensagem,
            "estado_atual": estado,
            "historico_recente": historico,
            "contexto_local": contexto,
            "observacao": "Use somente os dados fornecidos. Se não souber, pergunte ou chame humano.",
        }

        try:
            response = self.client.responses.create(
                model=self.settings.openai_model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "atendente_response",
                        "strict": True,
                        "schema": OUTPUT_SCHEMA,
                    }
                },
            )
        except Exception as exc:
            return self._erro_humano(
                observacao=f"Erro na chamada OpenAI: {type(exc).__name__}: {exc}",
                motivo="Falha na chamada da OpenAI. Verifique OPENAI_API_KEY, OPENAI_MODEL e internet.",
            )

        text = self._extract_text(response)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            return self._erro_humano(
                observacao=f"JSON inválido da IA: {exc}. Texto recebido: {text[:500]}",
                motivo="Erro ao processar resposta estruturada da IA.",
            )

    def _extract_text(self, response: Any) -> str:
        if hasattr(response, "output_text") and response.output_text:
            return str(response.output_text)

        if hasattr(response, "model_dump"):
            data = response.model_dump()
        elif isinstance(response, dict):
            data = response
        else:
            return str(response)

        parts: list[str] = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if isinstance(content, dict) and content.get("text"):
                    parts.append(str(content["text"]))
        return "\n".join(parts).strip()

    def _normalizar_resposta(self, data: dict[str, Any]) -> dict[str, Any]:
        dados_lista = data.get("dados_coletados") or []
        dados_dict: dict[str, Any] = {}
        if isinstance(dados_lista, list):
            for item in dados_lista:
                if isinstance(item, dict) and item.get("campo"):
                    dados_dict[str(item["campo"])] = item.get("valor")
        elif isinstance(dados_lista, dict):
            dados_dict = dados_lista

        acoes = data.get("acoes") or []
        if not acoes:
            acoes = [
                {
                    "tipo": "nenhuma",
                    "arquivo": None,
                    "legenda": None,
                    "produto_codigo": None,
                    "observacao": None,
                }
            ]

        return {
            "resposta_cliente": str(data.get("resposta_cliente") or "Pode me passar mais detalhes do que você precisa?"),
            "intencao": str(data.get("intencao") or "nao_identificada"),
            "etapa": str(data.get("etapa") or "triagem"),
            "dados_coletados": dados_dict,
            "proximas_perguntas": list(data.get("proximas_perguntas") or []),
            "acoes": acoes,
            "precisa_humano": bool(data.get("precisa_humano", False)),
            "motivo_humano": data.get("motivo_humano"),
        }

    def _fallback_sem_api(self, mensagem: str, contexto: dict[str, Any]) -> dict[str, Any]:
        produtos = contexto.get("produtos_relevantes", [])
        catalogos = contexto.get("catalogos_relevantes", [])
        produto = produtos[0] if produtos else {}

        acoes: list[dict[str, Any]] = []
        if produto.get("imagem_principal"):
            acoes.append(
                {
                    "tipo": "enviar_imagem",
                    "arquivo": produto.get("imagem_principal"),
                    "legenda": f"Imagem sugerida: {produto.get('nome', 'produto')}",
                    "produto_codigo": produto.get("codigo"),
                    "observacao": "Fallback sem OpenAI: ação sugerida por busca local.",
                }
            )
        if catalogos:
            acoes.append(
                {
                    "tipo": "enviar_documento",
                    "arquivo": catalogos[0].get("arquivo"),
                    "legenda": catalogos[0].get("nome"),
                    "produto_codigo": None,
                    "observacao": "Catálogo sugerido por busca local.",
                }
            )
        if not acoes:
            acoes.append({"tipo": "perguntar_dado", "arquivo": None, "legenda": None, "produto_codigo": None, "observacao": None})

        if produto:
            texto = (
                f"Temos o modelo {produto.get('nome')} que pode atender esse caso. "
                "Para eu te orientar melhor, quantas unidades você precisa e para qual data?"
            )
        else:
            texto = "Claro! Para eu te indicar o melhor modelo, você procura troféus, medalhas, placas ou outro personalizado?"

        return {
            "resposta_cliente": texto,
            "intencao": "orcamento_novo",
            "etapa": "triagem",
            "dados_coletados": [],
            "proximas_perguntas": ["Qual produto você procura?", "Quantas unidades?", "Para qual data?"],
            "acoes": acoes,
            "precisa_humano": False,
            "motivo_humano": None,
        }
