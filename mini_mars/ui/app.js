"use strict";

const $ = (id) => document.getElementById(id);
const canvas = $("board");
const ctx = canvas.getContext("2d");
const colors = ["#e48c5d", "#69c8ce"];
const state = { matches: [], match: null, replay: null, turn: 0, view: "full", timer: null, hover: null, loadToken: 0 };

function key(x, y) { return `${x},${y}`; }
function frame() { return state.replay?.frames[state.turn]; }
function showStatus(message) { $("status").textContent = message; $("status").hidden = false; }
function hideStatus() { $("status").hidden = true; }
function stop() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  $("play").innerHTML = "▶ <span>PLAY</span>";
  $("play").setAttribute("aria-label", "Play");
}
function setTurn(turn) {
  if (!state.replay) return;
  state.turn = Math.max(0, Math.min(state.replay.frames.length - 1, Number(turn) || 0));
  render();
  if (state.turn === state.replay.frames.length - 1) stop();
}
function start() {
  if (!state.replay) return;
  if (state.turn === state.replay.frames.length - 1) setTurn(0);
  stop();
  $("play").innerHTML = "Ⅱ <span>PAUSE</span>";
  $("play").setAttribute("aria-label", "Pause");
  state.timer = setInterval(() => setTurn(state.turn + 1), 1000 / Number($("speed").value));
}

async function refreshMatches(preferredId = null) {
  stop();
  showStatus("Loading saved matches…");
  try {
    const response = await fetch("/api/matches", { cache: "no-store" });
    if (!response.ok) throw new Error(`Match list: HTTP ${response.status}`);
    state.matches = (await response.json()).matches;
    const select = $("match-select");
    select.replaceChildren();
    for (const match of state.matches) {
      const option = document.createElement("option");
      option.value = match.id;
      option.textContent = `Seed ${match.seed} · ${(match.bots || ["Bot 0", "Bot 1"]).join(" vs ")}`;
      select.append(option);
    }
    if (!state.matches.length) {
      state.replay = null;
      $("workspace").hidden = true;
      $("result").textContent = "NO SAVED MATCHES";
      showStatus("No saved Mini Mars replay found. Run: python3 -m mini_mars match --bot-a greedy --bot-b coordinated --seed 42\nThen click Refresh.");
      return;
    }
    select.value = state.matches.some((match) => match.id === preferredId) ? preferredId : state.matches[0].id;
    await loadMatch(select.value);
  } catch (error) {
    $("workspace").hidden = true;
    showStatus(`Could not load matches: ${error.message}`);
  }
}

async function loadMatch(id) {
  stop();
  const token = ++state.loadToken;
  showStatus("Loading replay…");
  try {
    const response = await fetch(`/api/replay?id=${encodeURIComponent(id)}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Replay: HTTP ${response.status}`);
    const replay = await response.json();
    if (replay.format !== "mini-mars-replay-v1" || !Array.isArray(replay.frames) || !replay.frames.length) {
      throw new Error("Unsupported or empty Mini Mars replay");
    }
    if (token !== state.loadToken) return;
    state.replay = replay;
    state.match = state.matches.find((match) => match.id === id);
    state.turn = 0;
    state.hover = null;
    $("seed-label").textContent = replay.seed;
    $("map-size").textContent = `${replay.config.width} × ${replay.config.height} · ${replay.config.turns} turns`;
    $("scrubber").max = replay.frames.length - 1;
    const winner = replay.result.winner;
    $("result").textContent = winner === null ? `FINAL · TIE ${replay.result.scores.join("–")}` : `FINAL · PLAYER ${winner} WINS ${replay.result.scores.join("–")}`;
    drawScoreChart();
    drawNotableEvents();
    $("workspace").hidden = false;
    hideStatus();
    resizeCanvas();
    render();
  } catch (error) {
    if (token !== state.loadToken) return;
    state.replay = null;
    $("workspace").hidden = true;
    showStatus(`Could not load replay: ${error.message}`);
  }
}

function visibility() {
  const f = frame();
  const full = state.view === "full";
  const player = full ? null : Number(state.view);
  const known = full ? null : new Map(f.colonies[player].known.map((cell) => [key(cell.x, cell.y), cell]));
  const rocks = full ? new Set(state.replay.map.rocks.map((cell) => key(cell.x, cell.y))) : null;
  const deposits = full ? new Map(f.deposits.map((cell) => [key(cell.x, cell.y), cell])) : null;
  return { full, player, known, rocks, deposits };
}
function cellAt(x, y, fog) {
  if (!fog.full) return fog.known.get(key(x, y)) || null;
  const deposit = fog.deposits.get(key(x, y));
  return { x, y, terrain: fog.rocks.has(key(x, y)) ? "rock" : "plain", resource: deposit?.resource || null, quantity: deposit?.quantity || 0, visible: true };
}
function entityVisible(owner, x, y, fog) {
  return fog.full || owner === fog.player || fog.known.get(key(x, y))?.visible === true;
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  if (!rect.width) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  drawBoard();
}
function diamond(cx, cy, radius) {
  ctx.beginPath(); ctx.moveTo(cx, cy - radius); ctx.lineTo(cx + radius, cy);
  ctx.lineTo(cx, cy + radius); ctx.lineTo(cx - radius, cy); ctx.closePath();
}
function drawBoard() {
  if (!state.replay || !canvas.clientWidth) return;
  const { width, height } = state.replay.config;
  const f = frame();
  const fog = visibility();
  const boardWidth = canvas.clientWidth;
  const boardHeight = canvas.clientHeight;
  const tw = boardWidth / width, th = boardHeight / height;
  ctx.clearRect(0, 0, boardWidth, boardHeight);
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const cell = cellAt(x, y, fog);
      const px = x * tw, py = y * th;
      ctx.fillStyle = !cell ? "#0c171d" : cell.terrain === "rock" ? "#63727a" : cell.visible ? "#344a4a" : "#23353a";
      ctx.fillRect(px + .5, py + .5, tw - 1, th - 1);
      if (!cell) continue;
      if (cell.terrain === "rock") {
        ctx.strokeStyle = cell.visible ? "#9caaa9" : "#74878a";
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(px + tw * .29, py + th * .29); ctx.lineTo(px + tw * .71, py + th * .71);
        ctx.moveTo(px + tw * .71, py + th * .29); ctx.lineTo(px + tw * .29, py + th * .71); ctx.stroke();
      } else if (cell.resource && cell.quantity > 0) {
        ctx.globalAlpha = cell.visible ? 1 : .46;
        ctx.fillStyle = cell.resource === "gold" ? "#efb95e" : "#b5cbd0";
        diamond(px + tw * .5, py + th * .48, Math.min(tw, th) * .28); ctx.fill();
        ctx.fillStyle = "#192c32";
        ctx.font = `700 ${Math.max(9, Math.min(14, tw * .32))}px Consolas, monospace`;
        ctx.fillText(String(cell.quantity), px + tw * .5, py + th * .49);
        ctx.globalAlpha = 1;
      }
    }
  }
  for (let owner = 0; owner < 2; owner++) {
    for (const base of f.colonies[owner].bases) {
      if (!entityVisible(owner, base.x, base.y, fog)) continue;
      const px = base.x * tw, py = base.y * th;
      diamond(px + tw * .5, py + th * .5, Math.min(tw, th) * .34);
      ctx.fillStyle = "#1b2b32"; ctx.fill();
      ctx.lineWidth = 3; ctx.strokeStyle = colors[owner]; ctx.stroke();
    }
  }
  const groups = new Map();
  for (const rover of f.rovers) {
    if (!entityVisible(rover.player, rover.x, rover.y, fog)) continue;
    const id = `${rover.player}:${key(rover.x, rover.y)}`;
    if (!groups.has(id)) groups.set(id, { owner: rover.player, x: rover.x, y: rover.y, count: 0 });
    groups.get(id).count++;
  }
  for (const group of groups.values()) {
    const px = group.x * tw, py = group.y * th;
    const cx = px + tw * (group.owner === 0 ? .34 : .66), cy = py + th * .67;
    const radius = Math.min(tw, th) * .19;
    ctx.beginPath(); ctx.arc(cx, cy, radius + 2, 0, Math.PI * 2); ctx.fillStyle = "#18242b"; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, radius, 0, Math.PI * 2); ctx.fillStyle = colors[group.owner]; ctx.fill();
    ctx.fillStyle = "#15242a"; ctx.font = `800 ${Math.max(9, Math.min(13, tw * .29))}px Consolas, monospace`;
    ctx.fillText(group.count > 1 ? String(group.count) : String(group.owner), cx, cy + .5);
  }
  if (state.hover && state.hover.x >= 0 && state.hover.x < width && state.hover.y >= 0 && state.hover.y < height) {
    ctx.strokeStyle = "#fff1d3"; ctx.lineWidth = 2;
    ctx.strokeRect(state.hover.x * tw + 1, state.hover.y * th + 1, tw - 2, th - 2);
  }
}

function describeTile() {
  if (!state.replay || !state.hover) { $("tile-readout").textContent = "Hover over a cell to inspect it."; return; }
  const { x, y } = state.hover;
  const fog = visibility();
  const cell = cellAt(x, y, fog);
  if (!cell) { $("tile-readout").textContent = `(${x}, ${y}) · unexplored`; return; }
  const details = [`(${x}, ${y})`, cell.visible ? "visible" : `last seen turn ${cell.last_seen}`, cell.terrain];
  if (cell.resource && cell.quantity > 0) details.push(`${cell.quantity} ${cell.resource}${cell.visible ? "" : " (last seen)"}`);
  const bases = frame().colonies.flatMap((colony, owner) => colony.bases.filter((base) => base.x === x && base.y === y && entityVisible(owner, x, y, fog)).map(() => `P${owner} base`));
  const rovers = frame().rovers.filter((rover) => rover.x === x && rover.y === y && entityVisible(rover.player, x, y, fog)).map((rover) => `${rover.id} cargo: ${rover.cargo.gold} gold, ${rover.cargo.iron} iron`);
  $("tile-readout").textContent = details.concat(bases, rovers).join(" · ");
}

function renderCards() {
  const f = frame(), { width, height } = state.replay.config;
  const cards = $("colony-cards"); cards.replaceChildren();
  for (let owner = 0; owner < 2; owner++) {
    const colony = f.colonies[owner];
    const roverCount = f.rovers.filter((rover) => rover.player === owner).length;
    const card = document.createElement("div"); card.className = `colony-card ${owner ? "one" : "zero"}`;
    const head = document.createElement("div"); head.className = "colony-head";
    const marker = document.createElement("i"); head.append(marker, document.createTextNode(`PLAYER ${owner}`));
    const name = document.createElement("div"); name.className = "bot-name"; name.textContent = state.match?.bots?.[owner] || `Bot ${owner}`;
    const score = document.createElement("div"); score.className = "score"; score.textContent = colony.bank.gold;
    const unit = document.createElement("small"); unit.textContent = " BANKED GOLD"; score.append(unit);
    const stats = document.createElement("div"); stats.className = "card-stats";
    for (const [label, value] of [["Iron", colony.bank.iron], ["Rovers", roverCount], ["Bases", colony.bases.length], ["Explored", `${Math.round(colony.known.length / (width * height) * 100)}%`]]) {
      const item = document.createElement("div"); const span = document.createElement("span"); span.textContent = label; const strong = document.createElement("strong"); strong.textContent = value; item.append(span, strong); stats.append(item);
    }
    card.append(head, name, score, stats); cards.append(card);
  }
}
function drawScoreChart() {
  const frames = state.replay.frames;
  const max = Math.max(1, ...frames.flatMap((f) => f.colonies.map((colony) => colony.bank.gold)));
  for (let owner = 0; owner < 2; owner++) {
    const d = frames.map((f, i) => `${i ? "L" : "M"}${(i * 320 / Math.max(1, frames.length - 1)).toFixed(2)},${(96 - f.colonies[owner].bank.gold * 88 / max).toFixed(2)}`).join(" ");
    $(`score-${owner ? "one" : "zero"}`).setAttribute("d", d);
  }
}
function eventText(event) {
  const owner = event.rover_id?.match(/^p(\d+)/)?.[1];
  const who = owner === undefined ? "Rover" : `P${owner} ${event.rover_id}`;
  if (event.type === "mine") return `${who} mined ${event.quantity} ${event.resource}`;
  if (event.type === "deposit") return `${who} delivered ${event.gold} gold, ${event.iron} iron`;
  if (event.type === "build") return `P${event.player} built a base at (${event.x}, ${event.y})`;
  if (event.type === "mine_contested") return `${who} lost a contested mine`;
  return `${event.type || "Event"} · ${event.rover_id || "colony"}`;
}
function drawNotableEvents() {
  const list = $("event-list"); list.replaceChildren();
  const notable = [];
  state.replay.frames.forEach((f, index) => {
    for (const event of f.events) if (event.type !== "mine") notable.push({ index, text: eventText(event) });
    for (const item of f.diagnostics) notable.push({ index, text: `Invalid action: ${item.reason || item.type || "check log"}` });
  });
  if (!notable.length) { const empty = document.createElement("p"); empty.className = "empty"; empty.textContent = "No deposits, builds, contests, or invalid actions recorded."; list.append(empty); return; }
  for (const item of notable) {
    const button = document.createElement("button"); button.type = "button"; button.className = "event-button";
    button.dataset.turn = item.index;
    const turn = document.createElement("span"); turn.textContent = `T${String(item.index).padStart(2, "0")}`;
    button.append(turn, document.createTextNode(item.text));
    button.addEventListener("click", () => { stop(); setTurn(item.index); });
    list.append(button);
  }
}
function drawCurrentEvents() {
  const f = frame(); const list = $("current-events"); list.replaceChildren();
  const events = [...f.events.map(eventText), ...f.diagnostics.map((item) => `Invalid action: ${item.reason || item.type || "check log"}`)];
  if (!events.length) { const empty = document.createElement("p"); empty.className = "empty"; empty.textContent = f.turn === 0 ? "Rovers are at their starting bases." : "No mining, deposits, builds, or diagnostics this turn."; list.append(empty); return; }
  for (const label of events.slice(0, 7)) { const row = document.createElement("div"); row.className = "current-event"; row.textContent = label; list.append(row); }
  if (events.length > 7) { const more = document.createElement("div"); more.className = "empty"; more.textContent = `+ ${events.length - 7} more events`; list.append(more); }
}
function render() {
  if (!state.replay) return;
  const max = state.replay.frames.length - 1;
  const turn = frame().turn;
  $("scrubber").value = state.turn;
  $("scrubber").style.setProperty("--progress", `${state.turn * 100 / Math.max(1, max)}%`);
  $("turn-label").textContent = `TURN ${turn} / ${max}`;
  $("current-turn").textContent = String(turn).padStart(2, "0");
  $("turn-phase").textContent = turn === 0 ? "Landing state" : turn === max ? "Final state" : "Turn resolved";
  $("score-cursor").setAttribute("x1", String(state.turn * 320 / Math.max(1, max)));
  $("score-cursor").setAttribute("x2", String(state.turn * 320 / Math.max(1, max)));
  for (const button of $("event-list").querySelectorAll("button")) button.classList.toggle("active", Number(button.dataset.turn) === state.turn);
  $("first").disabled = $("previous").disabled = state.turn === 0;
  $("next").disabled = $("last").disabled = state.turn === max;
  renderCards(); drawCurrentEvents(); drawBoard(); describeTile();
}

canvas.addEventListener("mousemove", (event) => {
  if (!state.replay) return;
  const rect = canvas.getBoundingClientRect();
  const x = Math.floor((event.clientX - rect.left) / rect.width * state.replay.config.width);
  const y = Math.floor((event.clientY - rect.top) / rect.height * state.replay.config.height);
  if (x < 0 || y < 0 || x >= state.replay.config.width || y >= state.replay.config.height) return;
  if (state.hover?.x === x && state.hover?.y === y) return;
  state.hover = { x, y }; drawBoard(); describeTile();
});
canvas.addEventListener("mouseleave", () => { state.hover = null; drawBoard(); describeTile(); });
$("refresh").addEventListener("click", () => refreshMatches($("match-select").value));
$("match-select").addEventListener("change", (event) => loadMatch(event.target.value));
$("perspective").addEventListener("change", (event) => { state.view = event.target.value; drawBoard(); describeTile(); });
$("scrubber").addEventListener("input", (event) => { stop(); setTurn(event.target.value); });
$("first").addEventListener("click", () => { stop(); setTurn(0); });
$("previous").addEventListener("click", () => { stop(); setTurn(state.turn - 1); });
$("next").addEventListener("click", () => { stop(); setTurn(state.turn + 1); });
$("last").addEventListener("click", () => { stop(); setTurn(state.replay.frames.length - 1); });
$("play").addEventListener("click", () => state.timer ? stop() : start());
$("speed").addEventListener("change", () => { if (state.timer) start(); });
document.addEventListener("keydown", (event) => {
  if (!state.replay || ["SELECT", "INPUT", "BUTTON"].includes(document.activeElement?.tagName)) return;
  if (event.key === "ArrowLeft") { event.preventDefault(); stop(); setTurn(state.turn - 1); }
  if (event.key === "ArrowRight") { event.preventDefault(); stop(); setTurn(state.turn + 1); }
  if (event.code === "Space") { event.preventDefault(); state.timer ? stop() : start(); }
});
window.addEventListener("resize", resizeCanvas);
refreshMatches();
