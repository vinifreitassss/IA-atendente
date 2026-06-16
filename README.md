# IA Atendente — alpha 0.0.1

Motor local de conversação para atendimento comercial da Silva Campos Esportes.

Este alpha foi feito para rodar no PC da fábrica, na porta `6060`, com um chat web local para testar a IA antes de conectar ao WhatsApp.

## Objetivo do alpha

Validar o núcleo da atendente:

- conversar com o cliente em um chat local;
- consultar produtos, catálogos, regras da empresa, scripts e objeções em CSV;
- responder sem inventar preço, prazo ou produto;
- sugerir envio de imagens e PDFs desde o começo;
- gerar ações estruturadas para depois plugar no WhatsApp;
- montar rascunhos de pedido, sem fechar pedido automaticamente nesta fase.

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite o `.env` e coloque sua chave:

```env
OPENAI_API_KEY=sua_chave_aqui
```

Depois rode:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 6060 --reload
```

No PC servidor:

```text
http://localhost:6060
```

Em outros PCs via Hamachi:

```text
http://IP_DO_HAMACHI_DO_PC_SERVIDOR:6060
```

## Estrutura

```text
app/
  main.py          # rotas FastAPI e app web
  ai_client.py     # integração com OpenAI e resposta estruturada
  config.py        # variáveis de ambiente
  schemas.py       # contratos da API
  storage.py       # SQLite: conversas, mensagens e estado
  tools.py         # leitura/busca em CSVs e arquivos locais

data/
  empresa.csv          # regras gerais da empresa
  produtos.csv         # produtos, imagens, catálogos e dados técnicos
  objecoes.csv         # quebra de objeções
  scripts.csv          # roteiro comercial por etapa
  campos_pedido.csv    # campos que a IA precisa coletar
  catalogos.csv        # catálogos PDF e quando enviar

midia/
  produtos/        # fotos dos produtos

catalogos/
  PDFs dos catálogos

static/
  index.html       # chat local
  app.js
  styles.css
```

## Regra importante

A IA não envia arquivo sozinha. Ela sugere ações como:

```json
{
  "tipo": "enviar_imagem",
  "arquivo": "midia/produtos/TROF-001/foto1.jpg",
  "legenda": "Modelo de troféu MDF 15cm"
}
```

No chat local isso aparece como anexo sugerido. Quando conectarmos ao WhatsApp, o conector do WhatsApp executará essa ação.

## Como preencher as planilhas

### `data/produtos.csv`

Campos principais:

- `ativo`: `sim` ou `nao`;
- `codigo`: código único do produto;
- `nome`: nome comercial;
- `categoria`: troféu, medalha, placa etc.;
- `descricao_comercial`: explicação para cliente;
- `descricao_visual`: aparência do produto;
- `preco_base`: preço inicial ou observação;
- `preco_por_quantidade`: regra simples para quantidade;
- `quantidade_minima`;
- `medidas_produto_mm`;
- `area_personalizacao`;
- `material`;
- `acabamento`;
- `prazo_producao`;
- `peso_g`;
- `dimensoes_embalagem_cm`;
- `imagem_principal`: caminho local da foto;
- `imagens_extras`: caminhos separados por `|`;
- `catalogo_pdf`: caminho do PDF;
- `tags`: palavras que ajudam a IA a escolher;
- `quando_oferecer`: situações ideais;
- `restricoes`: o que não prometer;
- `perguntas_para_orcamento`: perguntas necessárias.

### `data/objecoes.csv`

Use para cadastrar objeções reais dos clientes:

- “está caro”;
- “preciso para amanhã”;
- “quero ver modelos”;
- “não tenho arte”;
- “faz desconto?”;
- “vi mais barato em outro lugar”.

Sempre preencha também `limite_negociacao` e `chamar_humano`, para impedir a IA de prometer o que não deve.

### `data/catalogos.csv`

Use para o envio de PDFs:

- catálogo de troféus MDF;
- catálogo de medalhas;
- catálogo de acrílico;
- catálogo geral.

A IA deve enviar catálogo quando o cliente pedir modelos, estiver indeciso ou quiser comparar opções.

## Próximos passos depois do alpha

1. Testar a atendente no chat local.
2. Ajustar CSVs até ela responder bem.
3. Criar botão de “aprovar resposta”.
4. Conectar ao WhatsApp.
5. Transformar ações sugeridas em envios reais.
6. Integrar rascunho de pedido, frete, pagamento e layout.
