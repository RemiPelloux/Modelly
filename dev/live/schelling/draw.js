// The two views: agents in space and model reporters over time, drawn on canvases.

// Okabe-Ito, the palette Modelly's figures use (modelly.viz.palettes.OKABE_ITO).
export const PALETTE = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"];
const MARGIN = 36;
const DOT = 3;
const PAD = 0.05;

function extent(points, bounds) {
  if (bounds) return bounds;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const dx = (x1 - x0 || 1) * PAD;
  const dy = (y1 - y0 || 1) * PAD;
  return [x0 - dx, y0 - dy, x1 + dx, y1 + dy];
}

// A blue-to-orange ramp for a numeric attribute; grey for agents without a value.
function ramp(value, low, high) {
  if (value === null) return "#bbbbbb";
  const t = high > low ? (value - low) / (high - low) : 0.5;
  return `hsl(${220 - 190 * t} 70% ${45 + 10 * t}%)`;
}

function legend(element, entries) {
  element.replaceChildren(...entries.map(([colour, text]) => {
    const span = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.style.background = colour;
    span.append(swatch, text);
    return span;
  }));
}

export function drawSpace(canvas, caption, space) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!space) return void (caption.textContent = "No agent has a place in space.");
  const [x0, y0, x1, y1] = extent(space.points, space.bounds);
  const scale = Math.min(canvas.width / (x1 - x0), canvas.height / (y1 - y0));
  const values = space.points.map((p) => p[2]).filter((v) => v !== null);
  const [low, high] = [Math.min(...values), Math.max(...values)];
  const colour = space.classes.length
    ? (v) => PALETTE[v % PALETTE.length]
    : (v) => ramp(v, low, high);
  for (const [x, y, value] of space.points) {
    ctx.fillStyle = colour(value);
    const [px, py] = [(x - x0) * scale, (y - y0) * scale];
    if (space.cells) ctx.fillRect(px, py, Math.max(scale, 1), Math.max(scale, 1));
    else ctx.beginPath(), ctx.arc(px, py, DOT, 0, 2 * Math.PI), ctx.fill();
  }
  legend(caption, space.classes.length
    ? space.classes.map((name, i) => [colour(i), name])
    : [[ramp(low, low, high), `${low}`], [ramp(high, low, high), `${high}`]]);
}

export function drawPlot(canvas, caption, series) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const names = Object.keys(series);
  if (!names.length) return void (caption.textContent = "The model collects no numeric reporter.");
  const all = names.flatMap((name) => series[name]).filter((v) => v !== null);
  const [low, high] = [Math.min(...all), Math.max(...all)];
  const length = Math.max(...names.map((name) => series[name].length));
  const x = (i) => MARGIN + (i / Math.max(length - 1, 1)) * (canvas.width - 2 * MARGIN);
  const y = (v) => canvas.height - MARGIN - ((v - low) / (high - low || 1)) * (canvas.height - 2 * MARGIN);
  ctx.fillStyle = "#4a5873";
  ctx.fillText(String(+high.toPrecision(4)), 2, MARGIN);
  ctx.fillText(String(+low.toPrecision(4)), 2, canvas.height - MARGIN);
  ctx.fillText(`${length - 1}`, canvas.width - MARGIN, canvas.height - MARGIN / 2);
  names.forEach((name, n) => {
    ctx.strokeStyle = PALETTE[n % PALETTE.length];
    ctx.beginPath();
    series[name].forEach((v, i) => v !== null && (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.stroke();
  });
  legend(caption, names.map((name, n) => [PALETTE[n % PALETTE.length], name]));
}
