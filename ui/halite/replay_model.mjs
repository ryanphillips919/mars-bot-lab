/** Reconstruct each start-of-turn state from Halite III's replay deltas. */
export function buildTimeline(replay) {
  const map = replay?.production_map;
  const frames = replay?.full_frames;
  if (!map || !Array.isArray(frames) || frames.length === 0 ||
      !Number.isInteger(map.width) || !Number.isInteger(map.height) ||
      map.width < 1 || map.height < 1 || !Array.isArray(map.grid) ||
      map.grid.length !== map.height || !Array.isArray(replay.players)) {
    throw new Error("This file is not a supported Halite III replay.");
  }

  const width = map.width;
  const height = map.height;
  const firstGrid = new Uint16Array(width * height);
  for (let y = 0; y < height; y += 1) {
    if (!Array.isArray(map.grid[y]) || map.grid[y].length !== width) {
      throw new Error("The replay map has inconsistent dimensions.");
    }
    for (let x = 0; x < width; x += 1) {
      firstGrid[y * width + x] = map.grid[y][x].energy;
    }
  }

  const playerIds = replay.players.map((player) => String(player.player_id));
  const grids = [firstGrid];
  const structures = [replay.players.map((player) => ({
    x: player.factory_location.x,
    y: player.factory_location.y,
    owner: String(player.player_id),
    type: "shipyard",
  }))];
  const banks = [];
  const cargo = [];
  const shipCounts = [];
  const events = [];

  for (let index = 0; index < frames.length; index += 1) {
    if (index > 0) {
      const grid = grids[index - 1].slice();
      for (const cell of frames[index - 1].cells || []) {
        if (cell.x >= 0 && cell.x < width && cell.y >= 0 && cell.y < height) {
          grid[cell.y * width + cell.x] = cell.production;
        }
      }
      grids.push(grid);
      const bases = structures[index - 1].slice();
      for (const event of frames[index - 1].events || []) {
        if (event.type === "construct" && event.location) {
          bases.push({
            x: event.location.x,
            y: event.location.y,
            owner: String(event.owner_id),
            type: "dropoff",
          });
        }
      }
      structures.push(bases);
    }

    const current = frames[index];
    const priorEnergy = index === 0 ? null : frames[index - 1].energy;
    const frameBanks = {};
    const frameCargo = {};
    const frameShips = {};
    for (const id of playerIds) {
      const player = replay.players.find((item) => String(item.player_id) === id);
      const ships = Object.values(current.entities?.[id] || {});
      frameBanks[id] = Number(priorEnergy?.[id] ?? player.energy ?? 0);
      frameCargo[id] = ships.reduce((sum, ship) => sum + Number(ship.energy || 0), 0);
      frameShips[id] = ships.length;
    }
    banks.push(frameBanks);
    cargo.push(frameCargo);
    shipCounts.push(frameShips);
    for (const event of current.events || []) {
      if (["spawn", "shipwreck", "construct", "capture"].includes(event.type)) {
        events.push({ frame: index, ...event });
      }
    }
  }

  return { width, height, playerIds, grids, structures, banks, cargo, shipCounts, events };
}
