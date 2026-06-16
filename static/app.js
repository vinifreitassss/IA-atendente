const messages = document.getElementById("messages");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const healthEl = document.getElementById("health");
const contextoEl = document.getElementById("contexto");
const newConversationBtn = document.getElementById("newConversation");

let conversationId = localStorage.getItem("ia_atendente_conversation_id") || null;

function addMessage(role, text, data = null) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = text;

  if (data) {
    const debug = data.debug || {};
    const tokens = debug.tokens || {};
    const tokenLine = tokens.total_tokens
      ? `Tokens: ${tokens.total_tokens} total (${tokens.input_tokens || "?"} entrada / ${tokens.output_tokens || "?"} saída)<br>`
      : `Tokens: não informado (${escapeHtml(debug.modo || "desconhecido")})<br>`;

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `
      <strong>Interno</strong><br>
      Modo: ${escapeHtml(debug.modo || "desconhecido")}<br>
      Modelo: ${escapeHtml(debug.modelo || "-")}<br>
      ${tokenLine}
      Intenção: ${escapeHtml(data.intencao)}<br>
      Etapa: ${escapeHtml(data.etapa)}<br>
      Precisa humano: ${data.precisa_humano ? "sim" : "não"}<br>
      ${data.motivo_humano ? `Motivo: ${escapeHtml(data.motivo_humano)}<br>` : ""}
    `;

    if (data.dados_coletados && Object.keys(data.dados_coletados).length) {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(data.dados_coletados, null, 2);
      meta.appendChild(pre);
    }

    if (data.acoes && data.acoes.length) {
      const actions = document.createElement("div");
      actions.className = "actions";
      data.acoes.forEach((action) => {
        const card = document.createElement("div");
        card.className = "action-card";
        const arquivo = action.arquivo || "";
        const href = arquivo.startsWith("http") ? arquivo : `/${arquivo}`;
        card.innerHTML = `
          <strong>${escapeHtml(action.tipo)}</strong>
          ${action.legenda ? `<div>${escapeHtml(action.legenda)}</div>` : ""}
          ${action.produto_codigo ? `<div>Produto: ${escapeHtml(action.produto_codigo)}</div>` : ""}
          ${arquivo ? `<a href="${escapeAttr(href)}" target="_blank">Abrir anexo sugerido</a>` : ""}
          ${action.observacao ? `<small>${escapeHtml(action.observacao)}</small>` : ""}
        `;
        actions.appendChild(card);
      });
      meta.appendChild(actions);
    }

    el.appendChild(meta);
  }

  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

async function loadStatus() {
  const [health, contexto] = await Promise.all([
    fetch("/api/health").then((r) => r.json()),
    fetch("/api/contexto").then((r) => r.json()),
  ]);

  healthEl.innerHTML = `
    OK: ${health.ok ? "sim" : "não"}<br>
    OpenAI: ${health.openai_configurada ? "configurada" : "sem chave — usando fallback"}<br>
    Modelo: ${escapeHtml(health.modelo)}
  `;

  contextoEl.innerHTML = Object.entries(contexto)
    .map(([key, value]) => `${escapeHtml(key)}: ${value}`)
    .join("<br>");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  input.value = "";
  addMessage("user", message);

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!response.ok) {
    addMessage("ai", "Erro ao chamar a API local.");
    return;
  }

  const data = await response.json();
  conversationId = data.conversation_id;
  localStorage.setItem("ia_atendente_conversation_id", conversationId);
  addMessage("ai", data.resposta_cliente, data);
});

newConversationBtn.addEventListener("click", () => {
  conversationId = null;
  localStorage.removeItem("ia_atendente_conversation_id");
  messages.innerHTML = "";
  addMessage("ai", "Nova conversa iniciada. Pode simular o cliente.");
});

loadStatus().catch(() => {
  healthEl.textContent = "Não foi possível carregar status.";
  contextoEl.textContent = "Não foi possível carregar contexto.";
});

addMessage("ai", "Pode simular a primeira mensagem do cliente. Exemplo: 'Boa tarde, quero troféus para campeonato infantil'.");
