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

    const list = document.getElementById("provinces-list");
    list.innerHTML = data.provinces.map(p =>
        `<div class="province-card"><strong>${p.name}</strong> (${p.id}) | 人口: ${p.population} | 库银: ${p.treasury}</div>`
    ).join("");
}

async function advanceTurn() {
    const res = await fetch("/api/turn/advance", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
        alert("错误: " + (data.detail || data.error));
        return;
    }
    refreshState();
    if (data.reports) {
        const list = document.getElementById("reports-list");
        list.innerHTML = Object.entries(data.reports).map(([id, md]) =>
            `<div class="report-item"><strong>${id}</strong>\n${md}</div>`
        ).join("");
    }
    loadReports();
}

async function loadAgents() {
    const res = await fetch("/api/agents");
    const agents = await res.json();
    const sel = document.getElementById("agent-select");
    sel.innerHTML = agents.map(a => `<option value="${a}">${a}</option>`).join("");
}

async function sendChat() {
    const input = document.getElementById("chat-input");
    const agentId = document.getElementById("agent-select").value;
    if (!input.value.trim() || !agentId) return;

    const msg = input.value.trim();
    input.value = "";

    appendChat("player", msg);

    const res = await fetch(`/api/agents/${agentId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
    });
    const data = await res.json();
    if (res.ok) {
        appendChat("agent", data.response);
    } else {
        appendChat("agent", "[错误] " + (data.detail || data.error));
    }
}

function appendChat(role, text) {
    const container = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = "chat-msg " + role;
    div.textContent = (role === "player" ? "你: " : "臣: ") + text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
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
    const list = document.getElementById("reports-list");
    if (reports.length > 0) {
        list.innerHTML = reports.map(r =>
            `<div class="report-item"><strong>${r.agent_id}</strong> (回合 ${r.turn})\n${r.markdown}</div>`
        ).join("");
    }
}

async function loadCommands() {
    const res = await fetch("/api/commands");
    const cmds = await res.json();
    const list = document.getElementById("commands-list");
    list.innerHTML = cmds.map(c =>
        `<div class="province-card">${c.command_type} → ${c.target_province_id || "全国"} ${c.has_result ? "✓" : "待执行"}</div>`
    ).join("");
}
