// The three models behind the home page hero, drawn across the whole band.
// Each is make(w, h) -> { step(), draw(ctx), poke(x, y), set(value), count() }:
// poke is the visitor's pointer at canvas position (x, y), set the hero's slider.
"use strict";

window.ModellyHero = (function () {
  const rand = Math.random, pick = (n) => Math.floor(rand() * n);
  const INK = { bg: "#0f1a2e", s: [38, 56, 104], i: [255, 79, 139], r: [47, 212, 167], a: [108, 140, 255] };

  // A grid painted one pixel per cell, then scaled up without smoothing.
  function pixels(cols, rows) {
    const img = new ImageData(cols, rows), off = document.createElement("canvas");
    off.width = cols; off.height = rows;
    return {
      set(k, rgb) { const p = k * 4; img.data[p] = rgb[0]; img.data[p + 1] = rgb[1]; img.data[p + 2] = rgb[2]; img.data[p + 3] = 255; },
      blit(ctx, w, h) {
        off.getContext("2d").putImageData(img, 0, 0);
        ctx.imageSmoothingEnabled = false; ctx.drawImage(off, 0, 0, w, h);
      },
    };
  }

  // Susceptible, infected, recovered on a torus; immunity wanes back to susceptible.
  function epidemic(w, h) {
    const CELL = 8, cols = Math.ceil(w / CELL), rows = Math.ceil(h / CELL), n = cols * rows;
    const sir = window.ModellySims.makeSirs(cols, rows, { beta: 0.12, infected: 6, immune: 12 });
    const px = pixels(cols, rows);
    sir.seed(Math.round(n / 300));
    for (let j = 0; j < 90; j++) sir.step();
    return {
      step() { sir.step(); },
      draw(ctx) {
        for (let k = 0; k < n; k++) px.set(k, window.ModellySims.cellColor(sir, k));
        px.blit(ctx, cols * CELL, rows * CELL);
      },
      poke(x, y) {
        const cx = Math.floor(x / CELL), cy = Math.floor(y / CELL);
        for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
          const xx = cx + dx, yy = cy + dy;
          if (xx >= 0 && xx < cols && yy >= 0 && yy < rows && dx * dx + dy * dy < 6) sir.infect(yy * cols + xx);
        }
      },
      set(v) { sir.opts.beta = v; },
      count() { return n; },
    };
  }

  // Boids: align with, move toward and keep apart from the flock in sight; flee the pointer.
  function flocking(w, h) {
    const N = Math.round(Math.min(900, (w * h) / 1400)), SPEED = 2.2, CELL = 60;
    let vision = 34, threat = null;
    const boids = Array.from({ length: N }, () => {
      const a = rand() * 6.283;
      return { x: rand() * w, y: rand() * h, vx: Math.cos(a) * SPEED, vy: Math.sin(a) * SPEED };
    });
    const cols = Math.ceil(w / CELL), buckets = new Map();
    function index() {
      buckets.clear();
      for (const b of boids) {
        const k = Math.floor(b.y / CELL) * cols + Math.floor(b.x / CELL);
        (buckets.get(k) || buckets.set(k, []).get(k)).push(b);
      }
    }
    function steer(b) {
      let ax = 0, ay = 0, cx = 0, cy = 0, sx = 0, sy = 0, k = 0;
      const gx = Math.floor(b.x / CELL), gy = Math.floor(b.y / CELL), r = Math.ceil(vision / CELL);
      for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) {
        for (const o of buckets.get((gy + dy) * cols + gx + dx) || []) {
          const ox = o.x - b.x, oy = o.y - b.y, d2 = ox * ox + oy * oy;
          if (o === b || d2 > vision * vision) continue;
          k++; ax += o.vx; ay += o.vy; cx += ox; cy += oy;
          if (d2 < 256) { sx -= ox / (d2 + 1); sy -= oy / (d2 + 1); }
        }
      }
      if (k) { b.vx += (ax / k - b.vx) * 0.06 + cx / k * 0.008 + sx * 2; b.vy += (ay / k - b.vy) * 0.06 + cy / k * 0.008 + sy * 2; }
      if (threat) {
        const tx = b.x - threat.x, ty = b.y - threat.y, d2 = tx * tx + ty * ty;
        if (d2 < 140 * 140) { b.vx += tx / (d2 + 1) * 40; b.vy += ty / (d2 + 1) * 40; }
      }
      const v = Math.hypot(b.vx, b.vy) || 1, cap = threat ? SPEED * 1.8 : SPEED;
      b.vx = b.vx / v * Math.min(v, cap); b.vy = b.vy / v * Math.min(v, cap);
      if (v < SPEED * 0.6) { b.vx *= 1.1; b.vy *= 1.1; }
    }
    return {
      step() {
        index(); boids.forEach(steer);
        for (const b of boids) { b.x = (b.x + b.vx + w) % w; b.y = (b.y + b.vy + h) % h; }
        threat = null;
      },
      draw(ctx) {
        ctx.fillStyle = "rgba(15, 26, 46, 0.42)"; ctx.fillRect(0, 0, w, h);
        for (const [color, fast] of [["#6c8cff", false], ["#2fd4a7", true]]) {
          ctx.fillStyle = color; ctx.beginPath();
          for (const b of boids) {
            const v = Math.hypot(b.vx, b.vy) || 1;
            if ((v > SPEED * 1.15) !== fast) continue;
            const ux = b.vx / v, uy = b.vy / v;  // an arrowhead along the heading
            ctx.moveTo(b.x + ux * 6, b.y + uy * 6);
            ctx.lineTo(b.x - ux * 4 - uy * 3.5, b.y - uy * 4 + ux * 3.5);
            ctx.lineTo(b.x - ux * 2, b.y - uy * 2);
            ctx.lineTo(b.x - ux * 4 + uy * 3.5, b.y - uy * 4 - ux * 3.5);
            ctx.closePath();
          }
          ctx.fill();
        }
      },
      poke(x, y) { threat = { x, y }; },
      set(v) { vision = v; },
      count() { return N; },
    };
  }

  // Schelling: a resident moves to a random empty cell while too few neighbours match it.
  function segregation(w, h) {
    const CELL = 10, cols = Math.ceil(w / CELL), rows = Math.ceil(h / CELL), n = cols * rows;
    let homophily = 0.5;
    const grid = new Uint8Array(n), px = pixels(cols, rows), MOVES = Math.round(n / 12);
    const scramble = (k) => { grid[k] = rand() < 0.1 ? 0 : 1 + pick(2); };
    for (let k = 0; k < n; k++) scramble(k);
    function unhappy(k) {
      const x = k % cols, y = (k - x) / cols, me = grid[k];
      let same = 0, all = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if (!dx && !dy) continue;
        const o = grid[((y + dy + rows) % rows) * cols + ((x + dx + cols) % cols)];
        if (o) { all++; if (o === me) same++; }
      }
      return all > 0 && same / all < homophily;
    }
    const colors = [INK.s.map((v) => v * 0.55), INK.a, INK.i];
    return {
      step() {
        const empty = [];
        for (let k = 0; k < n; k++) if (!grid[k]) empty.push(k);
        for (let j = 0; j < MOVES; j++) {
          const k = pick(n);
          if (!grid[k] || !unhappy(k)) continue;
          const slot = pick(empty.length), to = empty[slot];
          grid[to] = grid[k]; grid[k] = 0; empty[slot] = k;
        }
      },
      draw(ctx) {
        for (let k = 0; k < n; k++) px.set(k, colors[grid[k]]);
        px.blit(ctx, cols * CELL, rows * CELL);
      },
      poke(x, y) {
        const cx = Math.floor(x / CELL), cy = Math.floor(y / CELL);
        for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
          const xx = cx + dx, yy = cy + dy;
          if (xx >= 0 && xx < cols && yy >= 0 && yy < rows && dx * dx + dy * dy < 17) scramble(yy * cols + xx);
        }
      },
      set(v) { homophily = v; },
      count() { let k = 0; for (const v of grid) if (v) k++; return k; },
    };
  }

  return { epidemic, flocking, segregation, background: INK.bg };
})();
