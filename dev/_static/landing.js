// Home page behaviour: the use-case sketches, the install button, the benchmark reveal.
// The hero is docs/_static/hero.js.
// Loaded on every page; does nothing unless the page holds .ml-landing.
"use strict";

(function () {
  const SKETCH_MS = 90;
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
    root.querySelectorAll("canvas[data-sim]").forEach(sketch);
    root.querySelectorAll("[data-copy]").forEach(copyInstall);
    // The benchmark plays once: armed only with JavaScript and motion allowed, so the
    // chart is complete without either.
    const bench = root.querySelector(".ml-dots");
    if (bench && !calm) {
      bench.classList.add("is-armed");
      const reveal = new IntersectionObserver((entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        // two frames: the hidden start is painted before the transition begins
        requestAnimationFrame(() => requestAnimationFrame(() => bench.classList.add("is-shown")));
        reveal.disconnect();
      }, { rootMargin: "0px 0px -30% 0px" });
      reveal.observe(bench);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
