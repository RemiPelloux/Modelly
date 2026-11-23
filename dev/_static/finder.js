// The home page's finder: type a task, the matching guides are listed under the field.
// Each guide carries the words people type for it; a guide matches when every word typed
// starts a word of its title or of its terms, best matches first. Enter searches the docs.
"use strict";

(function () {
  const GUIDES = [
    ["Getting started", "getting_started.html", "first model start learn tutorial install begin new"],
    ["Your first model, step by step", "tutorials/0_first_model.html", "tutorial agent step model beginner"],
    ["The model zoo", "zoo/index.html", "zoo example reference validated epidemic sir seir ecology economics traffic opinion"],
    ["Age-structured SEIR", "zoo/age_seir.html", "sir seir epidemic age contact matrix vaccination infection disease"],
    ["Within-host epidemic", "zoo/within_host.html", "virus viral host infection ode epidemic"],
    ["Coming from Mesa", "migrating_from_mesa.html", "mesa migrate codemod convert"],
    ["From NetLogo", "netlogo.html", "netlogo translate turtles patches"],
    ["Columns and fast models", "performance.html", "fast speed performance numpy columns vectorise large million"],
    ["Cohorts and vectorised phases", "vectorised_phases.html", "cohort counts vectorise binomial population fast"],
    ["Scaling up", "scale.html", "scale large million big memory"],
    ["ODEs in every agent", "agent_odes.html", "ode differential equation solve_ivp continuous events delay stochastic sde"],
    ["Coupling fields and ODEs", "coupling.html", "field diffusion pde ode stock flow system dynamics hybrid"],
    ["Geospatial models", "geospatial.html", "map gis raster geographic streets osm census spatial"],
    ["Networks", "networks.html", "network graph contact multilayer temporal"],
    ["Synthetic populations", "population.html", "population census households synthetic ipf"],
    ["Language-model agents", "llm_agents.html", "llm gpt claude language model agent memory conversation chatbot ai"],
    ["Experiments and sweeps", "experiments.html", "sweep experiment replicate parameter grid batch cluster slurm dask ray"],
    ["Calibration", "calibration.html", "calibrate fit data abc posterior bayesian estimate parameters"],
    ["Sensitivity analysis", "sensitivity.html", "sensitivity sobol morris variance parameters"],
    ["Emulators", "emulators.html", "emulator surrogate gaussian process history matching"],
    ["Decisions", "decide.html", "decide strategy policy compare cost effectiveness intervention robust optimise vaccination"],
    ["Causes and explanations", "explain.html", "cause effect counterfactual attribution shapley explain why"],
    ["Live data and assimilation", "assimilation.html", "data assimilation particle filter kalman forecast live stream"],
    ["Differentiable models", "differentiable.html", "gradient jax differentiable autodiff"],
    ["Running on a GPU", "gpu.html", "gpu cuda cupy jax fast"],
    ["Split runs across machines", "distributed.html", "distributed mpi cluster parallel partition"],
    ["Reproducible studies", "provenance.html", "reproduce reproducible manifest bundle zenodo verify archive paper"],
    ["Checkpoints", "checkpoints.html", "checkpoint save load resume"],
    ["Time travel", "timetravel.html", "rewind replay branch diff debug"],
    ["Model cards", "model_cards.html", "card documentation validation intended use limits ethics"],
    ["The model hub", "hub.html", "hub publish share install doi cite zenodo"],
    ["Checking a model", "lint.html", "lint check bugs reproducibility mistakes"],
    ["Profiling a model", "profile.html", "profile slow time performance"],
    ["Studio", "studio.html", "studio browser gui interface no code visual dashboard compare report"],
    ["A model as a web page", "browser.html", "web browser pyodide share export html"],
    ["Figures and animations", "figures.html", "figure plot animation chart matplotlib"],
    ["From R and Julia", "r_and_julia.html", "r julia reticulate pythoncall"],
    ["Plugins", "plugins.html", "plugin extend entry point"],
    ["Course and teaching", "course/index.html", "course teach class students lecture classroom instructor"],
    ["Windows without admin rights", "windows_no_admin.html", "windows install admin proxy offline locked"],
    ["Accessibility and languages", "accessibility.html", "accessibility wcag screen reader language french spanish portuguese chinese translation"],
    ["Event ordering", "event_ordering.html", "event order schedule priority time tie"],
    ["Deprecations and 2.0", "deprecations.html", "deprecation upgrade 2.0 migrate warning"],
    ["What's new", "whats_new.html", "new release changes version"],
    ["API reference", "apis/api_main.html", "api reference class function"],
  ];
  const MAX = 6;

  function words(text) {
    return text.toLowerCase().split(/[^a-z0-9.]+/).filter(Boolean);
  }

  function score(guide, query) {
    const terms = words(guide[0] + " " + guide[2]);
    let total = 0;
    for (const q of query) {
      const hit = terms.findIndex((t) => t.startsWith(q));
      if (hit < 0) return 0;
      total += hit < words(guide[0]).length ? 3 : 1;
    }
    return total;
  }

  function render(list, query) {
    list.replaceChildren();
    if (!query.length) return;
    const found = GUIDES.map((g) => [score(g, query), g]).filter(([s]) => s > 0)
      .sort((a, b) => b[0] - a[0]).slice(0, MAX);
    for (const [, [title, href, terms]] of found) {
      const item = document.createElement("li"), link = document.createElement("a");
      const name = document.createElement("strong"), hint = document.createElement("span");
      link.href = href;
      name.textContent = title;
      hint.textContent = terms.split(" ").slice(0, 6).join(", ");
      link.append(name, hint);
      item.append(link);
      list.append(item);
    }
    if (!found.length) {
      const item = document.createElement("li"), link = document.createElement("a");
      link.href = "search.html?q=" + encodeURIComponent(query.join(" "));
      link.textContent = "No guide by that name: search the whole documentation";
      item.append(link);
      list.append(item);
    }
  }

  function start() {
    const input = document.getElementById("ml-find"), list = document.getElementById("ml-find-results");
    if (!input || !list) return;
    input.addEventListener("input", () => render(list, words(input.value)));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
