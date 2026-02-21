// 页面加载时刷新状态
document.addEventListener("DOMContentLoaded", () => {
    refreshState();
    loadAgents();
});

async function refreshState() {
    const res = await fetch("/api/state");
    const data = await res.json();
    document.getElementById("turn-display").textContent = "回合: " + data.current_turn;
    document.getElementById("phase-display").textContent = "阶段: " + data.phase;
    document.getElementById("treasury-display").textContent = "国库: " + data.imperial_treasury;

    // 从 /api/provinces 获取完整数据
    loadProvinces();
}

async function loadProvinces() {
    const res = await fetch("/api/provinces");
    const provinces = await res.json();
    const list = document.getElementById("provinces-list");
    list.innerHTML = provinces.map(p => `
        <div class="province-card" onclick="toggleProvince(this)">
            <div class="summary">
                <span class="name">${p.name}</span>
                <span class="metrics">
                    <span>👥 ${formatNumber(p.population)}</span>
                    <span>😊 ${p.happiness}</span>
                    <span>🌾 ${formatNumber(p.granary_stock)}</span>
                    <span>⚔️ ${formatNumber(p.garrison_size)}</span>
                    <span class="expand-icon">▶</span>
                </span>
            </div>
            <div class="details">
                <div class="detail-row">
                    <span class="detail-label">省份ID</span>
                    <span class="detail-value">${p.id}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">人口</span>
                    <span class="detail-value">${formatNumber(p.population)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">幸福度</span>
                    <span class="detail-value">${p.happiness}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">粮仓存量</span>
                    <span class="detail-value">${formatNumber(p.granary_stock)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">驻军规模</span>
                    <span class="detail-value">${formatNumber(p.garrison_size)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">地方库银</span>
                    <span class="detail-value">${formatNumber(p.local_treasury)}</span>
                </div>
            </div>
        </div>
    `).join("");
}

function toggleProvince(card) {
    card.classList.toggle("expanded");
}

function formatNumber(num) {
    // 格式化大数字，如 1000000 -> 1M
    const n = parseFloat(num);
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "K";
    return num;
}

async function advanceTurn() {
    const btn = document.getElementById("advance-btn");
    const originalText = btn.textContent;

    // 显示加载状态
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-spinner"></span>处理中...';

    try {
        const res = await fetch("/api/turn/advance", { method: "POST" });
        const data = await res.json();
        if (!res.ok) {
            alert("错误: " + (data.detail || data.error));
            return;
        }
        refreshState();
        if (data.reports) {
            renderReports(Object.entries(data.reports).map(([id, md]) => ({
                agent_id: id,
                turn: data.turn,
                markdown: md
            })));
        }
        loadReports();
    } finally {
        // 恢复按钮状态
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function loadAgents() {
    const res = await fetch("/api/agents");
    const agents = await res.json();
    const sel = document.getElementById("agent-select");
    sel.innerHTML = agents.map(a => `<option value="${a}">${a}</option>`).join("");
}

async function sendChat() {
    const input = document.getElementById("chat-input");
    const sendBtn = document.querySelector("#chat-input-row button");
    const agentId = document.getElementById("agent-select").value;
    if (!input.value.trim() || !agentId) return;

    const msg = input.value.trim();
    input.value = "";

    appendChat("player", msg);

    // 禁用发送按钮
    sendBtn.disabled = true;

    // 创建流式响应容器
    const responseDiv = appendStreamingResponse();

    try {
        const res = await fetch(`/api/agents/${agentId}/chat/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg }),
        });

        if (!res.ok) {
            const data = await res.json();
            responseDiv.innerHTML = "臣: [错误] " + (data.detail || data.error);
            return;
        }

        // 读取流式响应
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            // 解析 SSE 格式
            const lines = chunk.split("\n");
            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const data = line.slice(6);
                    if (data === "[DONE]") {
                        // 流结束，渲染 Markdown
                        responseDiv.className = "chat-msg agent";
                        responseDiv.innerHTML = "臣: " + renderMarkdown(fullText);
                    } else {
                        fullText += data;
                        // 实时更新（原始文本）
                        responseDiv.innerHTML = "臣: " + escapeHtml(fullText);
                        // 滚动到底部
                        const container = document.getElementById("chat-messages");
                        container.scrollTop = container.scrollHeight;
                    }
                }
            }
        }
    } catch (error) {
        responseDiv.innerHTML = "臣: [错误] " + error.message;
    } finally {
        sendBtn.disabled = false;
    }
}

function appendStreamingResponse() {
    const container = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = "chat-msg agent thinking";
    div.innerHTML = '臣: <span class="thinking-dots">正在思考</span>';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function appendChat(role, text) {
    const container = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = "chat-msg " + role;
    const prefix = role === "player" ? "你: " : "臣: ";
    div.innerHTML = prefix + renderMarkdown(text);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function appendThinking() {
    const container = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = "chat-msg agent thinking";
    div.innerHTML = '臣: <span class="thinking-dots">正在思考</span>';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

async function submitCommand(event) {
    event.preventDefault();
    const form = event.target;
    const body = {
        command_type: form.command_type.value,
        description: form.description.value,
        target_province_id: form.target_province_id.value || null,
        parameters: {},
        direct: form.direct.checked,
    };

    const res = await fetch("/api/commands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.ok) {
        form.reset();
        loadCommands();
    } else {
        alert("错误: " + (data.detail || data.error));
    }
}

async function loadReports() {
    const res = await fetch("/api/reports");
    const reports = await res.json();
    if (reports.length > 0) {
        renderReports(reports);
    }
}

function renderReports(reports) {
    const list = document.getElementById("reports-list");
    list.innerHTML = reports.map(r => `
        <div class="report-card" onclick="toggleReport(event, this)">
            <div class="header">
                <span class="agent-name">${r.agent_id}</span>
                <span>
                    <span class="turn-info">回合 ${r.turn}</span>
                    <span class="expand-icon">▶</span>
                </span>
            </div>
            <div class="content">
                <div class="markdown-body">${renderMarkdown(r.markdown)}</div>
            </div>
        </div>
    `).join("");
}

function toggleReport(event, card) {
    // 只有点击 header 区域才切换折叠，点击内容区域不切换
    if (event.target.closest(".content")) return;
    card.classList.toggle("expanded");
}

function renderMarkdown(text) {
    if (typeof marked !== "undefined") {
        return marked.parse(text);
    }
    // fallback: 简单换行处理
    return text.replace(/\n/g, "<br>");
}

async function loadCommands() {
    const res = await fetch("/api/commands");
    const cmds = await res.json();
    const list = document.getElementById("commands-list");
    list.innerHTML = cmds.map(c =>
        `<div class="province-card">${c.command_type} → ${c.target_province_id || "全国"} ${c.has_result ? "✓" : "待执行"}</div>`
    ).join("");
}
