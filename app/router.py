from __future__ import annotations

import re
from typing import Any

from app.tools import LocalTools, normalize


class LocalRouter:
    """Roteador local para economizar tokens em pedidos simples.

    Ele resolve perguntas diretas sem chamar OpenAI. A IA fica reservada para
    atendimento consultivo, orçamento, objeções e conversas ambíguas.
    """

    def __init__(self, tools: LocalTools) -> None:
        self.tools = tools

    def tentar_responder(self, mensagem: str, estado: dict[str, Any] | None = None) -> dict[str, Any] | None:
        texto = normalize(mensagem)
        estado = estado or {}

        if self._eh_horario(texto):
            return self._responder_horario()

        if self._eh_pagamento(texto):
            return self._responder_pagamento()

        if self._eh_catalogo(texto):
            return self._responder_catalogo(mensagem, estado)

        return None

    def _empresa_valor(self, chave: str, padrao: str = "") -> str:
        chave_norm = normalize(chave)
        for row in self.tools.empresa():
            if normalize(row.get("chave")) == chave_norm:
                return row.get("valor") or padrao
        return padrao

    def _eh_horario(self, texto: str) -> bool:
        termos = [
            "horario",
            "funcionamento",
            "abre",
            "fecha",
            "atendimento",
            "que horas",
            "ate que horas",
        ]
        return any(t in texto for t in termos)

    def _eh_pagamento(self, texto: str) -> bool:
        termos = [
            "pagamento",
            "pagar",
            "pix",
            "cartao",
            "boleto",
            "parcel",
            "forma de pagamento",
            "formas de pagamento",
        ]
        return any(t in texto for t in termos)

    def _eh_catalogo(self, texto: str) -> bool:
        termos_catalogo = ["catalogo", "catalogos", "pdf"]
        termos_modelo = ["modelo", "modelos", "foto", "fotos", "imagem", "imagens", "exemplo", "exemplos"]
        pedido_envio = ["manda", "mandar", "envia", "enviar", "ver", "mostra", "mostrar", "tem"]
        return any(t in texto for t in termos_catalogo) or (
            any(t in texto for t in termos_modelo) and any(t in texto for t in pedido_envio)
        )

    def _responder_horario(self) -> dict[str, Any]:
        horario = self._empresa_valor("horario_atendimento", "nosso horario ainda nao foi cadastrado no sistema")
        return {
            "resposta_cliente": f"Nosso horário de atendimento é: {horario}. Posso te ajudar com algum produto ou orçamento?",
            "intencao": "informar_horario",
            "etapa": "atendimento_informativo",
            "dados_coletados": [],
            "proximas_perguntas": ["Posso te ajudar com algum produto ou orçamento?"],
            "acoes": [
                {
                    "tipo": "nenhuma",
                    "arquivo": None,
                    "legenda": None,
                    "produto_codigo": None,
                    "observacao": "Respondido pelo roteador local, sem chamada OpenAI.",
                }
            ],
            "precisa_humano": False,
            "motivo_humano": None,
            "_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "_modo": "roteador_local",
        }

    def _responder_pagamento(self) -> dict[str, Any]:
        formas = self._empresa_valor("formas_pagamento", "as formas de pagamento ainda nao foram cadastradas no sistema")
        return {
            "resposta_cliente": f"Trabalhamos com as seguintes formas de pagamento: {formas}. Para fechar um orçamento, primeiro preciso confirmar o produto, a quantidade e a personalização.",
            "intencao": "informar_pagamento",
            "etapa": "atendimento_informativo",
            "dados_coletados": [],
            "proximas_perguntas": ["Qual produto e quantidade você precisa?"],
            "acoes": [
                {
                    "tipo": "nenhuma",
                    "arquivo": None,
                    "legenda": None,
                    "produto_codigo": None,
                    "observacao": "Respondido pelo roteador local, sem chamada OpenAI.",
                }
            ],
            "precisa_humano": False,
            "motivo_humano": None,
            "_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "_modo": "roteador_local",
        }

    def _responder_catalogo(self, mensagem: str, estado: dict[str, Any]) -> dict[str, Any]:
        catalogos = self.tools.buscar_catalogos(mensagem, limite=2)
        produtos = self.tools.buscar_produtos(mensagem, limite=3)

        # Se a mensagem for genérica, usa catálogo geral ou primeiro ativo.
        if not catalogos:
            todos = self.tools.catalogos()
            geral = [c for c in todos if "geral" in normalize(c.get("codigo", "") + " " + c.get("nome", ""))]
            catalogos = geral[:1] or todos[:1]

        acoes: list[dict[str, Any]] = []
        for catalogo in catalogos:
            if catalogo.get("arquivo"):
                acoes.append(
                    {
                        "tipo": "enviar_documento",
                        "arquivo": catalogo.get("arquivo"),
                        "legenda": catalogo.get("nome") or "Catálogo",
                        "produto_codigo": None,
                        "observacao": "Catálogo sugerido pelo roteador local, sem chamada OpenAI.",
                    }
                )

        # Se pediu modelos/fotos, também sugere imagens dos produtos encontrados.
        texto = normalize(mensagem)
        pediu_foto = any(t in texto for t in ["foto", "fotos", "imagem", "imagens", "modelo", "modelos", "exemplo", "exemplos"])
        if pediu_foto:
            for produto in produtos:
                if produto.get("imagem_principal"):
                    acoes.append(
                        {
                            "tipo": "enviar_imagem",
                            "arquivo": produto.get("imagem_principal"),
                            "legenda": produto.get("nome") or "Modelo sugerido",
                            "produto_codigo": produto.get("codigo"),
                            "observacao": "Imagem sugerida pelo roteador local, sem chamada OpenAI.",
                        }
                    )

        if not acoes:
            acoes.append(
                {
                    "tipo": "chamar_humano",
                    "arquivo": None,
                    "legenda": None,
                    "produto_codigo": None,
                    "observacao": "Cliente pediu catálogo/modelos, mas não há arquivo cadastrado.",
                }
            )
            precisa_humano = True
            motivo = "Nenhum catálogo ou imagem cadastrado para envio."
            resposta = "Eu vou pedir para uma pessoa da equipe te enviar os modelos certinhos, porque não encontrei o catálogo cadastrado aqui."
        else:
            precisa_humano = False
            motivo = None
            if pediu_foto and len(acoes) > 1:
                resposta = "Claro! Vou te mandar alguns modelos e também o catálogo para você comparar com calma."
            else:
                resposta = "Claro! Vou te mandar o catálogo para você ver os modelos com calma."

        dados = []
        produto_interesse = estado.get("dados_coletados", {}).get("produto_interesse") if isinstance(estado.get("dados_coletados"), dict) else None
        if produto_interesse:
            dados.append({"campo": "produto_interesse", "valor": produto_interesse})

        return {
            "resposta_cliente": resposta,
            "intencao": "enviar_catalogo_ou_modelos",
            "etapa": "produto",
            "dados_coletados": dados,
            "proximas_perguntas": ["Algum desses modelos te agradou?", "Quantas unidades você precisa?"],
            "acoes": acoes,
            "precisa_humano": precisa_humano,
            "motivo_humano": motivo,
            "_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "_modo": "roteador_local",
        }
