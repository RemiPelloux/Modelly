// The home page hero: a model runs across the whole band, the visitor picks which one,
// changes its parameter and pokes it with the pointer, and the deck shows the Python
// that parameter lives in. Does nothing unless the page holds .ml-hero[data-hero].
"use strict";

(function () {
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const MODELS = {
    epidemic: {
      ms: 80, how: "Click or drag anywhere on the band to infect people.",
      slider: { label: "Transmission", min: 0.04, max: 0.4, step: 0.01, value: 0.12, fmt: (v) => v.toFixed(2) },
      source: "zoo/index.html",
      code: `class Person(CellAgent):
    def step(self):
        if self.state != SUSCEPTIBLE:
            return
        near = self.cell.neighborhood.agents
        sick = sum(a.state == INFECTED for a in near)
        risk = 1 - (1 - {v}) ** sick
        if self.random.random() < risk:
            self.state = INFECTED`,
    },
    flocking: {
      ms: 0, how: "Move the pointer through the flock: the birds scatter, then regroup.",
      slider: { label: "Vision", min: 12, max: 70, step: 1, value: 34, fmt: (v) => String(v) },
      source: "examples/basic/boid_flockers.html",
      code: `from modelly.space.continuous import (
    ContinuousSpaceAgent,
)

class Boid(ContinuousSpaceAgent):
    ...  # cohere, separate, match

boid = Boid(model, space, position=(x, y),
            speed=2, vision={v}, separation=10,
            cohere=0.03, separate=0.015,
            match=0.05)`,
    },
    segregation: {
      ms: 60, how: "Drag across the band to scramble a neighbourhood.",
      slider: { label: "Wanted alike", min: 0.2, max: 0.8, step: 0.05, value: 0.5, fmt: (v) => v.toFixed(2) },
      source: "examples/basic/schelling.html",
      code: `class SchellingAgent(CellAgent):
    def assign_state(self):
        hood = self.cell.get_neighborhood(radius=1)
        neighbors = list(hood.agents)
        similar = [n for n in neighbors
                   if n.type == self.type]
        self.happy = (len(similar)
                      >= {v} * len(neighbors))

    def step(self):
        if not self.happy:
            grid = self.model.grid
            self.cell = grid.select_random_empty_cell()`,
    },
  };
  const KEYWORDS = /\b(class|def|if|for|in|not|return|from|import)\b/g;

  function highlight(code, value) {
    const safe = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return safe.replace(KEYWORDS, '<i class="ml-kw">$1</i>').replace("{v}", `<mark>${value}</mark>`);
  }

  function hero(band) {
    const canvas = band.querySelector(".ml-hero-world"), ctx = canvas.getContext("2d");
    const $ = (k) => band.querySelector(`[data-out="${k}"]`);
    const range = band.querySelector("[data-param]"), toggle = band.querySelector("[data-toggle]");
    let name = "epidemic", model = null, w = 0, h = 0, steps = 0, last = 0;
    let playing = !calm, visible = true, pointer = null;

    function build() {
      const dpr = window.devicePixelRatio || 1, box = canvas.getBoundingClientRect();
      w = box.width; h = box.height;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = window.ModellyHero.background; ctx.fillRect(0, 0, w, h);
      model = window.ModellyHero[name](w, h);
      model.set(Number(range.value));
      model.draw(ctx); report();
    }

    function report() {
      $("agents").textContent = model.count().toLocaleString("en");
      $("step").textContent = steps.toLocaleString("en");
    }

    function choose(next) {
      const spec = MODELS[next];
      name = next; steps = 0; band.dataset.model = next;
      band.querySelectorAll("[data-pick]").forEach((tab) => tab.setAttribute("aria-pressed", String(tab.dataset.pick === next)));
      Object.assign(range, { min: spec.slider.min, max: spec.slider.max, step: spec.slider.step, value: spec.slider.value });
      $("label").textContent = spec.slider.label;
      $("how").textContent = spec.how;
      $("source").href = spec.source;
      show(spec, false); build();
    }

    function show(spec, flash) {
      const value = spec.slider.fmt(Number(range.value));
      $("value").textContent = value;
      $("code").innerHTML = highlight(spec.code, value);
      if (flash) { const mark = $("code").querySelector("mark"); mark.classList.add("is-new"); }
    }

    function loop(now) {
      if (playing && visible && now - last >= MODELS[name].ms) {
        last = now;
        if (pointer) model.poke(pointer.x, pointer.y);
        model.step(); steps++; model.draw(ctx);
        if (steps % 4 === 0) report();
      }
      requestAnimationFrame(loop);
    }

    function track(ev) {
      if (ev.target.closest("a, button, input, label, .ml-deck")) { pointer = null; return; }
      const box = canvas.getBoundingClientRect();
      const at = { x: ev.clientX - box.left, y: ev.clientY - box.top };
      const hovering = name === "flocking" && ev.pointerType === "mouse";
      pointer = ev.buttons || hovering ? at : null;
      if (pointer) { band.classList.add("is-touched"); if (!playing) { model.poke(at.x, at.y); model.draw(ctx); } }
    }

    band.addEventListener("pointerdown", track);
    band.addEventListener("pointermove", track);
    ["pointerup", "pointerleave", "pointercancel"].forEach((t) => band.addEventListener(t, () => { pointer = null; }));
    band.querySelectorAll("[data-pick]").forEach((tab) => tab.addEventListener("click", () => choose(tab.dataset.pick)));
    range.addEventListener("input", () => { model.set(Number(range.value)); show(MODELS[name], true); });
    const label = () => { toggle.textContent = playing ? "Pause" : "Play"; toggle.setAttribute("aria-pressed", String(!playing)); };
    toggle.addEventListener("click", () => { playing = !playing; label(); });
    new IntersectionObserver((e) => { visible = e[0].isIntersecting; }).observe(band);
    let width = window.innerWidth;
    window.addEventListener("resize", () => {
      if (Math.abs(window.innerWidth - width) < 40) return;
      width = window.innerWidth; build();
    });
    label(); choose(name); requestAnimationFrame(loop);
  }

  function start() {
    if (!window.ModellyHero || !window.ModellySims) return;
    document.querySelectorAll(".ml-hero[data-hero]").forEach(hero);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
