// Small agent-based models drawn on the home page. Each one is a sketch of a Modelly
// playbook or example, written for a canvas: init(size), step(), draw(ctx, size).
"use strict";

window.ModellySims = (function () {
  const C = {
    bg: "#0f1a2e", s: "#6c8cff", sDim: "#22325a", i: "#ff4f8b", r: "#2fd4a7",
    grass: "#1f5a44", bare: "#152238", white: "#e7ecf5", edge: "#2a3a5c",
  };
  const rand = Math.random;
  const pick = (n) => Math.floor(rand() * n);

  // Synchronous SIRS on a Moore torus; shared with the hero.
  function makeSirs(cols, rows, opts) {
    const n = cols * rows;
    const o = Object.assign({ beta: 0.1, infected: 5, immune: 14 }, opts);
    let state = new Uint8Array(n), timer = new Uint16Array(n);
    let next = new Uint8Array(n), nextT = new Uint16Array(n);
    const counts = [n, 0, 0];
    function infect(k) {
      if (state[k] === 0) { state[k] = 1; timer[k] = o.infected; }
    }
    function seed(m) { for (let j = 0; j < m; j++) infect(pick(n)); }
    function exposed(x, y) {
      let k = 0;
      for (let dy = -1; dy <= 1; dy++) {
        const yy = ((y + dy + rows) % rows) * cols;
        for (let dx = -1; dx <= 1; dx++) {
          if ((dx || dy) && state[yy + ((x + dx + cols) % cols)] === 1) k++;
        }
      }
      return k;
    }
    function step() {
      counts[0] = counts[1] = counts[2] = 0;
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          const k = y * cols + x, st = state[k];
          let ns = st, nt = timer[k] > 0 ? timer[k] - 1 : 0;
          if (st === 0) {
            const e = exposed(x, y);
            if (e && rand() < 1 - Math.pow(1 - o.beta, e)) { ns = 1; nt = o.infected; }
          } else if (nt === 0) {
            ns = st === 1 ? 2 : 0;
            nt = st === 1 ? o.immune + pick(o.immune) : 0;
          }
          next[k] = ns; nextT[k] = nt; counts[ns]++;
        }
      }
      [state, next] = [next, state];
      [timer, nextT] = [nextT, timer];
      if (counts[1] === 0) seed(3);
    }
    seed(4);
    return { cols, rows, opts: o, counts, step, infect, seed,
      get state() { return state; }, get timer() { return timer; } };
  }

  function gridSketch(cols) {
    let sim, img;
    return {
      init() { sim = makeSirs(cols, cols, { beta: 0.14 }); img = new ImageData(cols, cols); },
      step() { sim.step(); },
      draw(ctx, size) {
        for (let k = 0; k < cols * cols; k++) {
          const c = cellColor(sim, k), p = k * 4;
          img.data[p] = c[0]; img.data[p + 1] = c[1]; img.data[p + 2] = c[2]; img.data[p + 3] = 255;
        }
        paintScaled(ctx, img, size);
      },
    };
  }

  // Recovered cells fade from green back to the susceptible blue as their immunity wanes.
  const RGB = { s: [34, 50, 90], i: [255, 79, 139], r: [47, 212, 167] };
  function cellColor(sim, k) {
    const st = sim.state[k];
    if (st !== 2) return st === 1 ? RGB.i : RGB.s;
    const f = Math.min(1, sim.timer[k] / (2 * sim.opts.immune));
    return RGB.s.map((v, j) => v + (RGB.r[j] - v) * f);
  }

  let scratch;
  function paintScaled(ctx, img, size) {
    scratch = scratch || document.createElement("canvas");
    scratch.width = img.width; scratch.height = img.height;
    scratch.getContext("2d").putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(scratch, 0, 0, size, size);
  }

  function predatorPrey() {
    const N = 30, REGROW = 24;
    let grass, sheep, wolves;
    const walk = (a) => { a.x = (a.x + pick(3) - 1 + N) % N; a.y = (a.y + pick(3) - 1 + N) % N; a.e -= 1; };
    const spawn = (k, e) => Array.from({ length: k }, () => ({ x: pick(N), y: pick(N), e }));
    function breed(list, p, cap) {
      const born = [];
      for (const a of list) if (rand() < p && list.length + born.length < cap) { a.e /= 2; born.push({ ...a }); }
      return list.concat(born).filter((a) => a.e > 0);
    }
    return {
      init() { grass = new Uint8Array(N * N).map(() => pick(REGROW)); sheep = spawn(120, 6); wolves = spawn(14, 20); },
      step() {
        for (let k = 0; k < grass.length; k++) if (grass[k] > 0) grass[k]--;
        const flock = new Map();
        for (const s of sheep) {
          walk(s);
          const k = s.y * N + s.x;
          if (grass[k] === 0) { grass[k] = REGROW; s.e += 4; }
          flock.set(k, s);
        }
        for (const w of wolves) {
          walk(w);
          const prey = flock.get(w.y * N + w.x);
          if (prey && prey.e > 0) { prey.e = 0; w.e += 18; }
        }
        sheep = breed(sheep, 0.05, 700);
        wolves = breed(wolves, 0.05, 160);
        if (wolves.length < 2) wolves = wolves.concat(spawn(6, 20));
        if (sheep.length < 10) sheep = sheep.concat(spawn(40, 6));
      },
      draw(ctx, size) {
        const c = size / N;
        for (let k = 0; k < grass.length; k++) {
          ctx.fillStyle = grass[k] === 0 ? C.grass : C.bare;
          ctx.fillRect((k % N) * c, Math.floor(k / N) * c, c + 0.5, c + 0.5);
        }
        dots(ctx, sheep, c, C.white, 0.28);
        dots(ctx, wolves, c, C.i, 0.42);
      },
    };
  }

  function dots(ctx, list, c, color, r) {
    ctx.fillStyle = color;
    for (const a of list) {
      ctx.beginPath(); ctx.arc((a.x + 0.5) * c, (a.y + 0.5) * c, c * r, 0, 6.283); ctx.fill();
    }
  }

  function flocking() {
    const N = 90, R = 22, SPEED = 1.6;
    let boids, size;
    return {
      init(s) {
        size = s;
        boids = Array.from({ length: N }, () => {
          const a = rand() * 6.283;
          return { x: rand() * s, y: rand() * s, vx: Math.cos(a), vy: Math.sin(a) };
        });
      },
      step() {
        for (const b of boids) {
          let ax = 0, ay = 0, cx = 0, cy = 0, sx = 0, sy = 0, k = 0;
          for (const o of boids) {
            const dx = o.x - b.x, dy = o.y - b.y, d2 = dx * dx + dy * dy;
            if (o === b || d2 > R * R) continue;
            k++; ax += o.vx; ay += o.vy; cx += dx; cy += dy;
            if (d2 < 36) { sx -= dx; sy -= dy; }
          }
          if (k) { b.vx += ax / k * 0.05 + cx / k * 0.004 + sx * 0.03; b.vy += ay / k * 0.05 + cy / k * 0.004 + sy * 0.03; }
          const v = Math.hypot(b.vx, b.vy) || 1;
          b.vx = b.vx / v * SPEED; b.vy = b.vy / v * SPEED;
        }
        for (const b of boids) { b.x = (b.x + b.vx + size) % size; b.y = (b.y + b.vy + size) % size; }
      },
      draw(ctx) {
        ctx.fillStyle = C.bg; ctx.fillRect(0, 0, size, size);
        ctx.strokeStyle = C.s; ctx.lineWidth = 1.6; ctx.lineCap = "round";
        ctx.beginPath();
        for (const b of boids) { ctx.moveTo(b.x, b.y); ctx.lineTo(b.x - b.vx * 3, b.y - b.vy * 3); }
        ctx.stroke();
      },
    };
  }

  function network() {
    const N = 64, K = 3;
    let nodes, edges, size, t;
    function reset() {
      nodes.forEach((n) => { n.st = 0; n.t = 0; });
      for (let j = 0; j < 2; j++) { const n = nodes[pick(N)]; n.st = 1; n.t = 6; }
    }
    return {
      init(s) {
        size = s; t = 0;
        nodes = Array.from({ length: N }, () => ({ x: 8 + rand() * (s - 16), y: 8 + rand() * (s - 16), nb: [] }));
        edges = [];
        nodes.forEach((a, i) => {
          const near = nodes.map((b, j) => [Math.hypot(a.x - b.x, a.y - b.y), j]).sort((p, q) => p[0] - q[0]);
          for (const [, j] of near.slice(1, K + 1)) { edges.push([i, j]); a.nb.push(j); nodes[j].nb.push(i); }
        });
        reset();
      },
      step() {
        if (++t % 2) return;
        const hit = nodes.map((n) => n.st === 0 && n.nb.some((j) => nodes[j].st === 1 && rand() < 0.35));
        nodes.forEach((n, i) => {
          if (hit[i]) { n.st = 1; n.t = 6; } else if (n.st === 1 && --n.t === 0) n.st = rand() < 0.5 ? 2 : 0;
        });
        if (!nodes.some((n) => n.st === 1)) reset();
      },
      draw(ctx) {
        ctx.fillStyle = C.bg; ctx.fillRect(0, 0, size, size);
        ctx.strokeStyle = C.edge; ctx.lineWidth = 1; ctx.beginPath();
        for (const [i, j] of edges) { ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(nodes[j].x, nodes[j].y); }
        ctx.stroke();
        for (const n of nodes) {
          ctx.fillStyle = [C.s, C.i, C.r][n.st];
          ctx.beginPath(); ctx.arc(n.x, n.y, n.st === 1 ? 3.6 : 2.6, 0, 6.283); ctx.fill();
        }
      },
    };
  }

  // Stage-structured insects: eggs, larvae, pupae, adults; sterile males released in campaigns.
  function insects() {
    const DAYS = 150, CAMPAIGN = 90, RELEASE = 1500;
    let pop, sterile, day, hist;
    return {
      init() { pop = [400, 300, 80, 120]; sterile = 0; day = 0; hist = []; },
      step() {
        const [e, l, p, a] = pop, releasing = Math.floor(day / CAMPAIGN) % 2 === 1;
        if (releasing && day % 6 === 0) sterile += RELEASE;
        const mated = a / (a + sterile + 1);
        pop = [
          e * 0.72 + a * 0.6 * mated,
          l * (0.86 - l / 2000) + e * 0.22,
          p * 0.78 + l * 0.1,
          a * 0.93 + p * 0.18,
        ].map((v) => Math.max(v, 0));
        sterile *= 0.82; day++;
        hist.push({ stages: pop.slice(), releasing });
        if (hist.length > DAYS) hist.shift();
      },
      draw(ctx, size) {
        ctx.fillStyle = C.bg; ctx.fillRect(0, 0, size, size);
        const top = Math.max(1, ...hist.map((h) => h.stages.reduce((s, v) => s + v, 0)));
        const colors = [C.sDim, C.s, C.r, C.i], w = size / DAYS;
        hist.forEach((h, x) => {
          let y = size;
          if (h.releasing) { ctx.fillStyle = "#1a2947"; ctx.fillRect(x * w, 0, w + 0.5, size); }
          h.stages.forEach((v, s) => {
            const hgt = (v / top) * size * 0.9;
            ctx.fillStyle = colors[s]; ctx.fillRect(x * w, y - hgt, w + 0.5, hgt); y -= hgt;
          });
        });
      },
    };
  }

  function schelling() {
    const N = 32, HOMOPHILY = 0.5, MOVES = 24;
    let grid, calm;
    const at = (x, y) => grid[((y + N) % N) * N + ((x + N) % N)];
    function unhappy(k) {
      const x = k % N, y = Math.floor(k / N), me = grid[k];
      let same = 0, all = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const o = (dx || dy) ? at(x + dx, y + dy) : 0;
        if (o) { all++; if (o === me) same++; }
      }
      return all > 0 && same / all < HOMOPHILY;
    }
    return {
      init() { grid = new Uint8Array(N * N).map(() => (rand() < 0.12 ? 0 : 1 + pick(2))); calm = 0; },
      step() {
        const movers = [], empty = [];
        grid.forEach((v, k) => { if (!v) empty.push(k); else if (unhappy(k)) movers.push(k); });
        for (let j = 0; j < Math.min(MOVES, movers.length); j++) {
          const from = movers[pick(movers.length)], slot = pick(empty.length), to = empty[slot];
          if (!grid[from]) continue;
          grid[to] = grid[from]; grid[from] = 0; empty[slot] = from;
        }
        calm = movers.length ? 0 : calm + 1;
        if (calm > 30) this.init();
      },
      draw(ctx, size) {
        const c = size / N;
        ctx.fillStyle = C.bg; ctx.fillRect(0, 0, size, size);
        grid.forEach((v, k) => {
          if (!v) return;
          ctx.fillStyle = v === 1 ? C.s : C.i;
          ctx.fillRect((k % N) * c + 0.5, Math.floor(k / N) * c + 0.5, c - 1, c - 1);
        });
      },
    };
  }

  return {
    makeSirs,
    cellColor,
    sketches: {
      epidemic: () => gridSketch(40), "predator-prey": predatorPrey, flocking,
      network, insects, schelling,
    },
  };
})();
