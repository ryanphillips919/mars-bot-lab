import { buildTimeline } from "./replay_model.mjs";

const $ = (id) => document.getElementById(id);
const colors = ["#f6a45d", "#68cbd0"];
const state = { matches: [], replay: null, timeline: null, frame: 0, playing: false, speed: 8,
  lastTick: 0, fraction: 0, hover: null, loadSerial: 0 };
const canvas = $("board");
const context = canvas.getContext("2d");
const formatter = new Intl.NumberFormat("en-US");

function showStatus(message) {
  $("status").textContent = message;
  $("status").hidden = !message;
}

async function getJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed (${response.status}).`);
  return response.json();
}

async function refreshMatches(preferredId = $("match-select").value) {
  showStatus("Looking for completed matches…");
  try {
    const data = await getJSON("/api/matches");
    state.matches = data.matches;
    const select = $("match-select");
    select.replaceChildren();
    for (const match of data.matches) {
      const score = match.scores || {};
      const label = `Seed ${match.seed} · ${match.map_width}×${match.map_height} · ${score.player_0 ?? "?"}–${score.player_1 ?? "?"} · ${match.id}`;
      select.add(new Option(label, match.id));
    }
    if (!data.matches.length) {
      pause();
      state.replay = null;
      state.timeline = null;
      $("workspace").hidden = true;
      $("seed-label").textContent = "—";
      $("result-pill").textContent = "No saved matches yet";
      showStatus("No completed Halite matches found. In another terminal, run make demo, then click Refresh.");
      return;
    }
    const chosen = data.matches.find((match) => match.id === preferredId) || data.matches[0];
    select.value = chosen.id;
    await loadMatch(chosen);
  } catch (error) {
    showStatus(`Could not list matches: ${error.message}`);
  }
}

async function loadMatch(match) {
  const serial = ++state.loadSerial;
  pause();
  showStatus(`Loading replay for seed ${match.seed}…`);
  try {
    const replay = await getJSON(`/api/replay?id=${encodeURIComponent(match.id)}`);
    const timeline = buildTimeline(replay);
    if (serial !== state.loadSerial) return;
    state.replay = replay;
    state.timeline = timeline;
    state.frame = 0;
    state.hover = null;
    $("workspace").hidden = false;
    $("seed-label").textContent = String(match.seed);
    $("map-label").textContent = `MAP ${timeline.width} × ${timeline.height}`;
    $("scrubber").max = String(replay.full_frames.length - 1);
    $("result-pill").textContent = `${match.winner?.replace("player_", "PLAYER ")?.toUpperCase() || "MATCH"} WINS · ${match.scores?.player_0 ?? "?"}–${match.scores?.player_1 ?? "?"}`;
    renderChart();
    resizeBoard();
    render();
    showStatus("");
  } catch (error) {
    if (serial === state.loadSerial) {
      $("workspace").hidden = true;
      showStatus(`Could not load replay: ${error.message}`);
    }
  }
}

function pause() {
  state.playing = false;
  state.lastTick = 0;
  state.fraction = 0;
  $("play").innerHTML = "▶ <span>PLAY</span>";
  $("play").setAttribute("aria-label", "Play");
}

function togglePlay() {
  if (!state.timeline) return;
  if (state.playing) {
    pause();
    return;
  }
  if (state.frame >= state.replay.full_frames.length - 1) seek(0);
  state.playing = true;
  state.lastTick = 0;
  $("play").innerHTML = "Ⅱ <span>PAUSE</span>";
  $("play").setAttribute("aria-label", "Pause");
}

function seek(frame) {
  if (!state.timeline) return;
  const end = state.replay.full_frames.length - 1;
  state.frame = Math.max(0, Math.min(end, Math.round(frame)));
  render();
}

function tick(timestamp) {
  if (state.playing && state.timeline) {
    if (state.lastTick) {
      state.fraction += (timestamp - state.lastTick) * state.speed / 1000;
      const steps = Math.floor(state.fraction);
      if (steps > 0) {
        state.fraction -= steps;
        seek(state.frame + steps);
        if (state.frame === state.replay.full_frames.length - 1) pause();
      }
    }
    state.lastTick = timestamp;
  }
  requestAnimationFrame(tick);
}

function playerName(id) {
  const player = state.replay.players.find((item) => String(item.player_id) === id);
  return player?.name || `Player ${id}`;
}

function renderPlayers() {
  const timeline = state.timeline;
  const frame = state.frame;
  const cards = $("player-cards");
  cards.replaceChildren();
  timeline.playerIds.forEach((id, index) => {
    const card = document.createElement("article");
    card.className = "player-card";
    card.style.setProperty("--player-color", colors[index % colors.length]);
    const heading = document.createElement("div");
    heading.className = "player-heading";
    const marker = document.createElement("span");
    marker.className = "player-marker";
    const title = document.createElement("div");
    const tag = document.createElement("span");
    tag.className = "player-tag";
    tag.textContent = `PLAYER ${id}`;
    const name = document.createElement("strong");
    name.textContent = playerName(id);
    title.append(tag, name);
    heading.append(marker, title);
    const balance = document.createElement("div");
    balance.className = "player-balance";
    balance.textContent = formatter.format(timeline.banks[frame][id]);
    const unit = document.createElement("div");
    unit.className = "balance-unit";
    unit.textContent = "HALITE IN BANK";
    const metrics = document.createElement("div");
    metrics.className = "player-metrics";
    const ships = document.createElement("span");
    ships.textContent = `${timeline.shipCounts[frame][id]} ships`;
    const cargo = document.createElement("span");
    cargo.textContent = `${formatter.format(timeline.cargo[frame][id])} cargo`;
    metrics.append(ships, cargo);
    card.append(heading, balance, unit, metrics);
    cards.append(card);
  });
}

function eventTitle(event) {
  if (event.type === "spawn") return `Player ${event.owner_id} launched a ship`;
  if (event.type === "shipwreck") return `Collision · ${event.ships?.length || 0} ships lost`;
  if (event.type === "construct") return `Player ${event.owner_id} built a dropoff`;
  if (event.type === "capture") return "Ship captured";
  return event.type;
}

function renderEvents() {
  const list = $("event-list");
  list.replaceChildren();
  const events = state.timeline.events;
  if (!events.length) {
    const empty = document.createElement("p");
    empty.className = "panel-note";
    empty.textContent = "No key events in this match.";
    list.append(empty);
    return;
  }
  const nextIndex = events.findIndex((event) => event.frame > state.frame);
  const pivot = nextIndex === -1 ? events.length : nextIndex;
  const start = Math.max(0, Math.min(pivot - 3, events.length - 6));
  for (const event of events.slice(start, start + 6)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `event-row ${event.frame === state.frame ? "current" : ""}`;
    const turn = document.createElement("span");
    turn.className = "event-turn";
    turn.textContent = `T${String(event.frame).padStart(3, "0")}`;
    const detail = document.createElement("span");
    detail.textContent = eventTitle(event);
    button.append(turn, detail);
    button.addEventListener("click", () => { pause(); seek(event.frame); });
    list.append(button);
  }
}

function renderChart() {
  if (!state.timeline) return;
  const banks = state.timeline.banks;
  const count = banks.length;
  let maxBank = 1;
  for (const row of banks) for (const id of state.timeline.playerIds) maxBank = Math.max(maxBank, row[id]);
  state.timeline.playerIds.slice(0, 2).forEach((id, index) => {
    const path = banks.map((row, frame) => `${frame === 0 ? "M" : "L"}${(frame * 400 / Math.max(1, count - 1)).toFixed(1)},${(92 - row[id] / maxBank * 85).toFixed(1)}`).join(" ");
    $(`chart-${index === 0 ? "zero" : "one"}`).setAttribute("d", path);
  });
}

function render() {
  if (!state.timeline) return;
  const end = state.replay.full_frames.length - 1;
  const frame = state.frame;
  const timeline = state.timeline;
  $("turn-label").textContent = `TURN ${frame} / ${end}`;
  $("stat-turn").textContent = `${frame} / ${end}`;
  $("stat-ships").textContent = String(Object.values(timeline.shipCounts[frame]).reduce((a, b) => a + b, 0));
  $("stat-bases").textContent = String(timeline.structures[frame].filter((base) => base.type === "dropoff").length);
  $("scrubber").value = String(frame);
  $("scrubber").style.setProperty("--progress", `${frame / Math.max(1, end) * 100}%`);
  $("progress-label").textContent = `${frame} OF ${end} TURNS`;
  const cursor = frame * 400 / Math.max(1, end);
  $("chart-cursor").setAttribute("x1", cursor);
  $("chart-cursor").setAttribute("x2", cursor);
  renderPlayers();
  renderEvents();
  drawBoard();
  renderTileInfo();
}

function blend(from, to, amount) {
  return from.map((value, index) => Math.round(value + (to[index] - value) * amount));
}

function terrainColor(halite) {
  const t = Math.max(0, Math.min(1, halite / (state.replay.GAME_CONSTANTS?.MAX_CELL_PRODUCTION || 1000)));
  const rgb = t < 0.42 ? blend([25, 36, 47], [105, 75, 60], t / 0.42)
    : blend([105, 75, 60], [230, 157, 83], (t - 0.42) / 0.58);
  return `rgb(${rgb.join(",")})`;
}

function resizeBoard() {
  if (!state.timeline || $("workspace").hidden) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  drawBoard();
}

function drawBoard() {
  if (!state.timeline) return;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const timeline = state.timeline;
  const cellWidth = width / timeline.width;
  const cellHeight = height / timeline.height;
  const grid = timeline.grids[state.frame];
  context.clearRect(0, 0, width, height);
  for (let y = 0; y < timeline.height; y += 1) {
    for (let x = 0; x < timeline.width; x += 1) {
      context.fillStyle = terrainColor(grid[y * timeline.width + x]);
      context.fillRect(x * cellWidth, y * cellHeight, Math.ceil(cellWidth + 0.2), Math.ceil(cellHeight + 0.2));
    }
  }
  if (cellWidth >= 10) {
    context.strokeStyle = "rgba(11, 19, 27, .20)";
    context.lineWidth = 1;
    context.beginPath();
    for (let x = 1; x < timeline.width; x += 1) {
      context.moveTo(x * cellWidth + .5, 0);
      context.lineTo(x * cellWidth + .5, height);
    }
    for (let y = 1; y < timeline.height; y += 1) {
      context.moveTo(0, y * cellHeight + .5);
      context.lineTo(width, y * cellHeight + .5);
    }
    context.stroke();
  }

  for (const base of timeline.structures[state.frame]) {
    const cx = (base.x + .5) * cellWidth;
    const cy = (base.y + .5) * cellHeight;
    const radius = Math.min(cellWidth, cellHeight) * .43;
    context.fillStyle = colors[Number(base.owner) % colors.length];
    context.strokeStyle = "#101a24";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(cx, cy - radius);
    context.lineTo(cx + radius, cy);
    context.lineTo(cx, cy + radius);
    context.lineTo(cx - radius, cy);
    context.closePath();
    context.fill();
    context.stroke();
    if (base.type === "shipyard") {
      context.fillStyle = "#14202a";
      context.fillRect(cx - radius * .16, cy - radius * .16, radius * .32, radius * .32);
    }
  }

  const occupied = new Map();
  const snapshot = state.replay.full_frames[state.frame];
  for (const [owner, ships] of Object.entries(snapshot.entities || {})) {
    for (const ship of Object.values(ships)) {
      const key = `${ship.x},${ship.y}`;
      const overlap = occupied.get(key) || 0;
      occupied.set(key, overlap + 1);
      const offset = overlap === 0 ? 0 : (overlap % 2 ? 1 : -1) * Math.min(cellWidth, cellHeight) * .16;
      const cx = (ship.x + .5) * cellWidth + offset;
      const cy = (ship.y + .5) * cellHeight + offset;
      const radius = Math.max(2, Math.min(cellWidth, cellHeight) * .26);
      context.fillStyle = colors[Number(owner) % colors.length];
      context.strokeStyle = "#111a23";
      context.lineWidth = 1.5;
      context.beginPath();
      context.arc(cx, cy, radius, 0, Math.PI * 2);
      context.fill();
      context.stroke();
      if (ship.energy > 0 && radius >= 3) {
        context.strokeStyle = "#fff3ce";
        context.lineWidth = Math.max(1.5, radius * .32);
        context.beginPath();
        context.arc(cx, cy, radius + 2.2, -Math.PI / 2,
          -Math.PI / 2 + Math.PI * 2 * Math.min(1, ship.energy / (state.replay.GAME_CONSTANTS?.MAX_ENERGY || 1000)));
        context.stroke();
      }
    }
  }

  for (const event of snapshot.events || []) {
    if (!event.location || !["shipwreck", "construct"].includes(event.type)) continue;
    const cx = (event.location.x + .5) * cellWidth;
    const cy = (event.location.y + .5) * cellHeight;
    context.strokeStyle = event.type === "shipwreck" ? "#ff5165" : "#f9e5bd";
    context.lineWidth = 2.5;
    context.beginPath();
    context.arc(cx, cy, Math.min(cellWidth, cellHeight) * .44, 0, Math.PI * 2);
    context.stroke();
  }
  if (state.hover) {
    context.strokeStyle = "#f9f5e9";
    context.lineWidth = 2;
    context.strokeRect(state.hover.x * cellWidth + 1, state.hover.y * cellHeight + 1, cellWidth - 2, cellHeight - 2);
  }
}

function renderTileInfo() {
  const tile = $("tile-info");
  if (!state.timeline || !state.hover) {
    tile.textContent = "Hover over a map cell to inspect it.";
    return;
  }
  const { x, y } = state.hover;
  const timeline = state.timeline;
  const halite = timeline.grids[state.frame][y * timeline.width + x];
  const ships = [];
  for (const [owner, group] of Object.entries(state.replay.full_frames[state.frame].entities || {})) {
    for (const [id, ship] of Object.entries(group)) {
      if (ship.x === x && ship.y === y) ships.push(`P${owner} ship #${id}: ${ship.energy} cargo`);
    }
  }
  const bases = timeline.structures[state.frame].filter((base) => base.x === x && base.y === y)
    .map((base) => `P${base.owner} ${base.type}`);
  tile.textContent = `(${x}, ${y}) · ${formatter.format(halite)} halite${[...bases, ...ships].length ? " · " + [...bases, ...ships].join(" · ") : ""}`;
}

canvas.addEventListener("pointermove", (event) => {
  if (!state.timeline) return;
  const rect = canvas.getBoundingClientRect();
  const x = Math.floor((event.clientX - rect.left) / rect.width * state.timeline.width);
  const y = Math.floor((event.clientY - rect.top) / rect.height * state.timeline.height);
  if (x < 0 || x >= state.timeline.width || y < 0 || y >= state.timeline.height) return;
  if (state.hover?.x === x && state.hover?.y === y) return;
  state.hover = { x, y };
  drawBoard();
  renderTileInfo();
});
canvas.addEventListener("pointerleave", () => { state.hover = null; drawBoard(); renderTileInfo(); });
$("refresh").addEventListener("click", () => refreshMatches());
$("match-select").addEventListener("change", () => {
  const match = state.matches.find((item) => item.id === $("match-select").value);
  if (match) loadMatch(match);
});
$("first").addEventListener("click", () => { pause(); seek(0); });
$("previous").addEventListener("click", () => { pause(); seek(state.frame - 1); });
$("play").addEventListener("click", togglePlay);
$("next").addEventListener("click", () => { pause(); seek(state.frame + 1); });
$("last").addEventListener("click", () => { pause(); seek(state.replay?.full_frames.length - 1 || 0); });
$("scrubber").addEventListener("input", (event) => { pause(); seek(Number(event.target.value)); });
$("speed").addEventListener("change", (event) => { state.speed = Number(event.target.value); });
document.addEventListener("keydown", (event) => {
  if (["SELECT", "INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if (event.code === "Space") { event.preventDefault(); togglePlay(); }
  if (event.code === "ArrowLeft") { event.preventDefault(); pause(); seek(state.frame - 1); }
  if (event.code === "ArrowRight") { event.preventDefault(); pause(); seek(state.frame + 1); }
});
new ResizeObserver(resizeBoard).observe(canvas);
requestAnimationFrame(tick);
refreshMatches();
