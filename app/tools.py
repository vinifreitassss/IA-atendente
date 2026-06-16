import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.config import get_settings


def normalize(text: Any) -> str:
    raw = str(text or "").lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return raw


def split_terms(text: str) -> set[str]:
    normalized = normalize(text)
    terms = re.findall(r"[a-z0-9]{3,}", normalized)
    stopwords = {
        "uma", "uns", "para", "com", "que", "por", "das", "dos", "vou",
        "quero", "queria", "preciso", "boa", "tarde", "bom", "dia", "noite",
    }
    return {t for t in terms if t not in stopwords}


class LocalTools:
    """Ferramentas locais que a IA pode consultar indiretamente.

    No alpha, fazemos a busca local antes da chamada da IA e entregamos contexto
    relevante. Depois, podemos migrar estas funções para tool calling real.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.data_dir = Path(settings.data_dir)
        self.media_dir = Path(settings.media_dir)
        self.catalog_dir = Path(settings.catalog_dir)

    def _read_csv(self, filename: str) -> list[dict[str, str]]:
        path = self.data_dir / filename
        if not path.exists():
            return []

        content = path.read_text(encoding="utf-8-sig")
        sample = content[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"

        rows: list[dict[str, str]] = []
        reader = csv.DictReader(content.splitlines(), dialect=dialect)
        for row in reader:
            cleaned = {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}
            if any(cleaned.values()):
                rows.append(cleaned)
        return rows

    def empresa(self) -> list[dict[str, str]]:
        return self._read_csv("empresa.csv")

    def produtos(self, only_active: bool = True) -> list[dict[str, str]]:
        rows = self._read_csv("produtos.csv")
        if not only_active:
            return rows
        return [r for r in rows if normalize(r.get("ativo", "sim")) != "nao"]

    def objecoes(self) -> list[dict[str, str]]:
        return self._read_csv("objecoes.csv")

    def scripts(self) -> list[dict[str, str]]:
        return self._read_csv("scripts.csv")

    def campos_pedido(self) -> list[dict[str, str]]:
        return self._read_csv("campos_pedido.csv")

    def catalogos(self) -> list[dict[str, str]]:
        rows = self._read_csv("catalogos.csv")
        return [r for r in rows if normalize(r.get("ativo", "sim")) != "nao"]

    def buscar_produtos(self, mensagem: str, limite: int = 5) -> list[dict[str, str]]:
        termos = split_terms(mensagem)
        scored: list[tuple[int, dict[str, str]]] = []

        for produto in self.produtos():
            texto_busca = " ".join(
                [
                    produto.get("codigo", ""),
                    produto.get("nome", ""),
                    produto.get("categoria", ""),
                    produto.get("linha", ""),
                    produto.get("descricao_comercial", ""),
                    produto.get("descricao_visual", ""),
                    produto.get("tags", ""),
                    produto.get("quando_oferecer", ""),
                ]
            )
            texto_norm = normalize(texto_busca)
            score = sum(3 if termo in normalize(produto.get("tags", "")) else 1 for termo in termos if termo in texto_norm)
            if score > 0:
                scored.append((score, produto))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limite]]

    def buscar_objecoes(self, mensagem: str, limite: int = 3) -> list[dict[str, str]]:
        termos = split_terms(mensagem)
        scored: list[tuple[int, dict[str, str]]] = []
        for objecao in self.objecoes():
            texto = " ".join(objecao.values())
            texto_norm = normalize(texto)
            score = sum(1 for termo in termos if termo in texto_norm)
            if score > 0:
                scored.append((score, objecao))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limite]]

    def buscar_catalogos(self, mensagem: str, limite: int = 3) -> list[dict[str, str]]:
        termos = split_terms(mensagem)
        scored: list[tuple[int, dict[str, str]]] = []
        for catalogo in self.catalogos():
            texto = " ".join(catalogo.values())
            texto_norm = normalize(texto)
            score = sum(1 for termo in termos if termo in texto_norm)
            if score > 0:
                scored.append((score, catalogo))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limite]]

    def file_exists(self, file_path: str | None) -> bool:
        if not file_path:
            return False
        path = Path(file_path)
        if path.is_absolute():
            return path.exists()
        return path.exists()

    def build_context(self, mensagem: str) -> dict[str, Any]:
        produtos = self.buscar_produtos(mensagem)
        catalogos = self.buscar_catalogos(mensagem)
        objecoes = self.buscar_objecoes(mensagem)

        # Se não encontrou produto, manda alguns ativos para a IA não ficar cega.
        if not produtos:
            produtos = self.produtos()[:5]

        return {
            "empresa": self.empresa(),
            "produtos_relevantes": produtos,
            "catalogos_relevantes": catalogos,
            "objecoes_relevantes": objecoes,
            "scripts": self.scripts(),
            "campos_pedido": self.campos_pedido(),
        }
