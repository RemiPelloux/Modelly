// Home page behaviour: the hero epidemic, the use-case sketches, the benchmark reveal.
// Loaded on every page; does nothing unless the page holds .ml-landing.
"use strict";

(function () {
  const TICK_MS = 70, SKETCH_MS = 90, CELL_PX = 7, PRE_TICKS = 90;
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function fitCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1, box = canvas.getBoundingClientRect();
    canvas.width = Math.round(box.width * dpr); canvas.height = Math.round(box.height * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w: box.width, h: box.height };
  }

  function whenVisible(el, onChange) {
    new IntersectionObserver((entries) => entries.forEach((e) => onChange(e.isIntersecting)),
      { rootMargin: "80px" }).observe(el);
  }

  function hero(lab) {
    const world = lab.querySelector(".ml-lab-world"), curve = lab.querySelector(".ml-lab-curve");
    const { ctx, w, h } = fitCanvas(world), plot = fitCanvas(curve);
    const cols = Math.floor(w / CELL_PX), rows = Math.floor(h / CELL_PX);
    const sim = window.ModellySims.makeSirs(cols, rows);
    const img = new ImageData(cols, rows), off = document.createElement("canvas");
    off.width = cols; off.height = rows;
    const history = [], out = (k) => lab.querySelector(`[data-out="${k}"]`);
    let ticks = 0, playing = !calm, visible = true, last = 0;

    function paint() {
      for (let k = 0; k < cols * rows; k++) {
        const c = window.ModellySims.cellColor(sim, k), p = k * 4;
        img.data[p] = c[0]; img.data[p + 1] = c[1]; img.data[p + 2] = c[2]; img.data[p + 3] = 255;
      }
      off.getContext("2d").putImageData(img, 0, 0);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(off, 0, 0, cols * CELL_PX, rows * CELL_PX);
      paintCurve();
      ["s", "i", "r"].forEach((k, j) => { out(k).textContent = sim.counts[j].toLocaleString("en"); });
      out("tick").textContent = ticks.toLocaleString("en");
    }

    function paintCurve() {
      const n = cols * rows, c = plot.ctx, step = plot.w / Math.max(history.length, 1);
      c.clearRect(0, 0, plot.w, plot.h);
      const layers = [["#2fd4a7", (s) => s[1] + s[2]], ["#ff4f8b", (s) => s[1]]];
      c.fillStyle = "#22325a"; c.fillRect(0, 0, history.length * step, plot.h);
      for (const [color, value] of layers) {
        c.fillStyle = color; c.beginPath(); c.moveTo(0, plot.h);
        history.forEach((s, x) => c.lineTo(x * step, plot.h - (value(s) / n) * plot.h));
        c.lineTo((history.length - 1) * step, plot.h); c.fill();
      }
    }

    function tick() {
      sim.step(); ticks++;
      history.push(sim.counts.slice());
      if (history.length > plot.w / 2) history.shift();
    }

    function loop(now) {
      if (playing && visible && now - last > TICK_MS) { last = now; tick(); paint(); }
      requestAnimationFrame(loop);
    }

    function infectAt(ev) {
      const box = world.getBoundingClientRect();
      const x = Math.floor((ev.clientX - box.left) / CELL_PX), y = Math.floor((ev.clientY - box.top) / CELL_PX);
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
        if (x + dx >= 0 && x + dx < cols && y + dy >= 0 && y + dy < rows) sim.infect((y + dy) * cols + x + dx);
      }
      lab.classList.add("is-touched"); paint();
    }

    world.addEventListener("pointerdown", (ev) => { world.setPointerCapture(ev.pointerId); infectAt(ev); });
    world.addEventListener("pointermove", (ev) => { if (ev.buttons) infectAt(ev); });
    lab.querySelector("[data-beta]").addEventListener("input", (ev) => {
      sim.opts.beta = Number(ev.target.value);
      out("beta").textContent = sim.opts.beta.toFixed(2);
    });
    const toggle = lab.querySelector("[data-toggle]");
    const label = () => { toggle.textContent = playing ? "Pause" : "Play"; toggle.setAttribute("aria-pressed", String(!playing)); };
    toggle.addEventListener("click", () => { playing = !playing; label(); });
    whenVisible(world, (v) => { visible = v; });
    for (let j = 0; j < PRE_TICKS; j++) tick();
    label(); paint(); requestAnimationFrame(loop);
  }

  function sketch(canvas) {
    const make = window.ModellySims.sketches[canvas.dataset.sim];
    if (!make) return;
    const { ctx, w } = fitCanvas(canvas), model = make();
    model.init(w);
    for (let j = 0; j < 40; j++) model.step();
    model.draw(ctx, w);
    if (calm) return;
    let visible = false, last = 0;
    whenVisible(canvas, (v) => { visible = v; });
    (function loop(now) {
      if (visible && now - last > SKETCH_MS) { last = now; model.step(); model.draw(ctx, w); }
      requestAnimationFrame(loop);
    })(0);
  }

  function copyInstall(button) {
    button.addEventListener("click", async () => {
      const hint = button.querySelector("em"), icon = hint.innerHTML;
      try { await navigator.clipboard.writeText(button.dataset.copy); hint.textContent = "Copied"; }
      catch (err) { hint.textContent = "Select and copy"; }
      setTimeout(() => { hint.innerHTML = icon; }, 1800);
    });
  }

  function start() {
    const root = document.querySelector(".ml-landing");
    if (!root || !window.ModellySims) return;
    root.querySelectorAll(".ml-lab").forEach(hero);
    root.querySelectorAll("canvas[data-sim]").forEach(sketch);
    root.querySelectorAll("[data-copy]").forEach(copyInstall);
    const bench = root.querySelector(".ml-bench");
    if (bench) whenVisible(bench, (v) => { if (v) bench.classList.add("is-shown"); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
