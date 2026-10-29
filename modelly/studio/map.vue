<template>
  <div class="modelly-map">
    <canvas
      ref="canvas"
      class="modelly-map-canvas"
      :style="`width: 100%; height: ${height}px; display: block; touch-action: none; background: #ffffff; cursor: grab;`"
    ></canvas>
    <div ref="info" class="modelly-map-info" style="font-size: 12px; color: #555555; padding: 4px 0">
      loading the map
    </div>
  </div>
</template>
<script>
// Modelly Studio's map: agents as points, network edges and region outlines as lines.
// WebGL draws them (hundreds of thousands at interactive rates); without WebGL, a Canvas 2D
// context draws the same scene, slower; without either, the text below the canvas says so.
// Everything is in this file: nothing is fetched from a CDN.
module.exports = {
  mounted() {
    this.view = null;
    this.arrays = null;
    this.setup();
    this.listen();
    this.load();
  },
  beforeDestroy() {
    if (this.resizer) this.resizer.disconnect();
  },
  beforeUnmount() {
    this.$options.beforeDestroy.call(this);
  },
  watch: {
    scene() {
      this.load();
    },
    point_size() {
      this.draw();
    },
  },
  // Only this exported object reaches the browser: helpers and constants are methods.
  methods: {
    shaders() {
      const vertex = `
attribute vec2 a_position;
attribute vec4 a_colour;
uniform vec2 u_scale;
uniform vec2 u_offset;
uniform float u_size;
varying vec4 v_colour;
void main() {
  gl_Position = vec4(a_position * u_scale + u_offset, 0.0, 1.0);
  gl_PointSize = u_size;
  v_colour = a_colour;
}`;
      const fragment = `
precision mediump float;
uniform float u_round;
varying vec4 v_colour;
void main() {
  if (u_round > 0.5) {
    vec2 d = gl_PointCoord - vec2(0.5);
    if (dot(d, d) > 0.25) discard;
  }
  gl_FragColor = v_colour;
}`;
      return { vertex: vertex, fragment: fragment };
    },
    style() {
      return {
        line: [0.45, 0.45, 0.45, 0.6],
        node: [0.6, 0.6, 0.6, 1.0],
        fitMargin: 0.95,
        zoomStep: 1.1,
      };
    },
    decode(text, Type) {
      if (!text) return new Type(0);
      const binary = atob(text);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return new Type(bytes.buffer);
    },
    hexColour(hex) {
      const value = parseInt(hex.slice(1, 7), 16);
      return [(value >> 16) & 255, (value >> 8) & 255, value & 255, 255];
    },
    compile(gl, type, source) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        throw new Error(gl.getShaderInfoLog(shader));
      }
      return shader;
    },
    setup() {
      const canvas = this.$refs.canvas;
      this.gl = null;
      this.ctx = null;
      this.mode = "none";
      if (!this.force_canvas) {
        try {
          this.gl = canvas.getContext("webgl", { preserveDrawingBuffer: true, antialias: true });
        } catch (error) {
          this.gl = null;
        }
      }
      if (this.gl) {
        try {
          this.program();
          this.mode = "webgl";
        } catch (error) {
          this.gl = null;
        }
      }
      if (!this.gl) {
        this.ctx = canvas.getContext("2d");
        this.mode = this.ctx ? "canvas2d" : "none";
      }
      canvas.dataset.renderer = this.mode;
    },
    program() {
      const gl = this.gl;
      const program = gl.createProgram();
      gl.attachShader(program, this.compile(gl, gl.VERTEX_SHADER, this.shaders().vertex));
      gl.attachShader(program, this.compile(gl, gl.FRAGMENT_SHADER, this.shaders().fragment));
      // Attribute 0 must be an enabled array on some drivers: make it the positions.
      gl.bindAttribLocation(program, 0, "a_position");
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(program));
      }
      gl.useProgram(program);
      this.locations = {
        position: gl.getAttribLocation(program, "a_position"),
        colour: gl.getAttribLocation(program, "a_colour"),
        scale: gl.getUniformLocation(program, "u_scale"),
        offset: gl.getUniformLocation(program, "u_offset"),
        size: gl.getUniformLocation(program, "u_size"),
        round: gl.getUniformLocation(program, "u_round"),
      };
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    },
    colours(classes, palette, given) {
      if (given.length) return given;
      const rgba = palette.map((hex) => this.hexColour(hex));
      const out = new Uint8Array(classes.length * 4);
      for (let i = 0; i < classes.length; i++) {
        const colour = rgba[classes[i] % rgba.length] || [0, 0, 0, 255];
        out.set(colour, i * 4);
      }
      return out;
    },
    load() {
      const scene = this.scene || {};
      const points = this.decode(scene.points, Float32Array);
      const classes = this.decode(scene.classes, Uint8Array);
      const given = this.decode(scene.colours, Uint8Array);
      this.arrays = {
        points: points,
        colours: this.colours(classes, scene.palette || [], given),
        nodes: this.decode(scene.nodes, Float32Array),
        segments: this.decode(scene.segments, Float32Array),
        extent: scene.extent || [1, 1],
      };
      if (this.gl) this.upload();
      if (!this.view || this.extentChanged()) this.fit();
      this.draw();
    },
    extentChanged() {
      const extent = this.arrays.extent;
      return !this.lastExtent || this.lastExtent[0] !== extent[0] || this.lastExtent[1] !== extent[1];
    },
    upload() {
      const gl = this.gl;
      const make = (array) => {
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, array, gl.STATIC_DRAW);
        return buffer;
      };
      if (this.buffers) Object.values(this.buffers).forEach((b) => gl.deleteBuffer(b));
      this.buffers = {
        points: make(this.arrays.points),
        colours: make(this.arrays.colours),
        nodes: make(this.arrays.nodes),
        segments: make(this.arrays.segments),
      };
    },
    resize() {
      const canvas = this.$refs.canvas;
      const ratio = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
      const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
    },
    fit() {
      this.resize();
      const canvas = this.$refs.canvas;
      const extent = this.arrays.extent;
      const width = extent[0] || 1;
      const height = extent[1] || 1;
      const scale = this.style().fitMargin * Math.min(canvas.width / width, canvas.height / height);
      this.view = { x: width / 2, y: height / 2, scale: scale };
      this.lastExtent = extent.slice();
      this.sized = canvas.clientWidth > 0;
    },
    draw() {
      if (!this.arrays || !this.view) return;
      const started = performance.now();
      this.resize();
      try {
        if (this.gl) this.drawWebgl();
        else if (this.ctx) this.drawCanvas();
      } catch (error) {
        this.mode = "error";
        this.$refs.canvas.dataset.renderer = "error";
        this.$refs.info.textContent = `the map could not be drawn: ${error}`;
        return;
      }
      this.report(performance.now() - started);
    },
    report(elapsed) {
      const canvas = this.$refs.canvas;
      const points = this.arrays.points.length / 2;
      const lines = this.arrays.segments.length / 4;
      canvas.dataset.points = points;
      canvas.dataset.segments = lines;
      canvas.dataset.drawMs = elapsed.toFixed(1);
      const how = { webgl: "WebGL", canvas2d: "Canvas 2D (no WebGL)", none: "no canvas" }[this.mode];
      this.$refs.info.textContent =
        `${how}: ${points} agents, ${this.arrays.nodes.length / 2} nodes, ${lines} lines, ` +
        `drawn in ${elapsed.toFixed(0)} ms. Drag to pan, scroll to zoom, double-click to fit.`;
    },
    attribute(buffer, location, size, type, normalised) {
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, size, type, normalised, 0, 0);
    },
    drawWebgl() {
      const gl = this.gl;
      const loc = this.locations;
      const canvas = this.$refs.canvas;
      const view = this.view;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(1, 1, 1, 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
      const sx = (2 * view.scale) / canvas.width;
      const sy = (2 * view.scale) / canvas.height;
      gl.uniform2f(loc.scale, sx, sy);
      gl.uniform2f(loc.offset, -view.x * sx, -view.y * sy);
      gl.disableVertexAttribArray(loc.colour);
      gl.uniform1f(loc.round, 0);
      gl.vertexAttrib4f(loc.colour, ...this.style().line);
      this.attribute(this.buffers.segments, loc.position, 2, gl.FLOAT, false);
      gl.drawArrays(gl.LINES, 0, this.arrays.segments.length / 2);
      const ratio = window.devicePixelRatio || 1;
      gl.uniform1f(loc.round, 1);
      gl.uniform1f(loc.size, Math.max(1, this.point_size * ratio * 0.6));
      gl.vertexAttrib4f(loc.colour, ...this.style().node);
      this.attribute(this.buffers.nodes, loc.position, 2, gl.FLOAT, false);
      gl.drawArrays(gl.POINTS, 0, this.arrays.nodes.length / 2);
      gl.uniform1f(loc.size, Math.max(1, this.point_size * ratio));
      this.attribute(this.buffers.colours, loc.colour, 4, gl.UNSIGNED_BYTE, true);
      this.attribute(this.buffers.points, loc.position, 2, gl.FLOAT, false);
      gl.drawArrays(gl.POINTS, 0, this.arrays.points.length / 2);
    },
    drawCanvas() {
      const ctx = this.ctx;
      const canvas = this.$refs.canvas;
      const view = this.view;
      const px = (x) => (x - view.x) * view.scale + canvas.width / 2;
      const py = (y) => canvas.height / 2 - (y - view.y) * view.scale;
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      const segments = this.arrays.segments;
      ctx.strokeStyle = "rgba(115, 115, 115, 0.6)";
      ctx.beginPath();
      for (let i = 0; i < segments.length; i += 4) {
        ctx.moveTo(px(segments[i]), py(segments[i + 1]));
        ctx.lineTo(px(segments[i + 2]), py(segments[i + 3]));
      }
      ctx.stroke();
      const ratio = window.devicePixelRatio || 1;
      this.dots(this.arrays.nodes, null, this.point_size * ratio * 0.6, px, py);
      this.dots(this.arrays.points, this.arrays.colours, this.point_size * ratio, px, py);
    },
    dots(points, colours, size, px, py) {
      const ctx = this.ctx;
      const half = size / 2;
      ctx.fillStyle = "rgb(153, 153, 153)";
      let last = -1;
      for (let i = 0; i < points.length / 2; i++) {
        if (colours) {
          const key = (colours[4 * i] << 16) | (colours[4 * i + 1] << 8) | colours[4 * i + 2];
          if (key !== last) {
            ctx.fillStyle = `rgba(${colours[4 * i]}, ${colours[4 * i + 1]}, ${colours[4 * i + 2]}, ${colours[4 * i + 3] / 255})`;
            last = key;
          }
        }
        ctx.fillRect(px(points[2 * i]) - half, py(points[2 * i + 1]) - half, size, size);
      }
    },
    listen() {
      const canvas = this.$refs.canvas;
      const ratio = () => window.devicePixelRatio || 1;
      let drag = null;
      canvas.addEventListener("pointerdown", (event) => {
        drag = { x: event.clientX, y: event.clientY };
        canvas.setPointerCapture(event.pointerId);
      });
      canvas.addEventListener("pointermove", (event) => {
        if (!drag || !this.view) return;
        this.view.x -= ((event.clientX - drag.x) * ratio()) / this.view.scale;
        this.view.y += ((event.clientY - drag.y) * ratio()) / this.view.scale;
        drag = { x: event.clientX, y: event.clientY };
        this.draw();
      });
      canvas.addEventListener("pointerup", () => {
        drag = null;
      });
      canvas.addEventListener("dblclick", () => {
        this.fit();
        this.draw();
      });
      canvas.addEventListener("wheel", (event) => this.zoom(event), { passive: false });
      if (window.ResizeObserver) {
        if (this.resizer) this.resizer.disconnect();
        this.resizer = new ResizeObserver(() => {
          if (this.arrays && !this.sized) this.fit(); // mounted before it had a size
          this.draw();
        });
        this.resizer.observe(canvas);
      }
    },
    zoom(event) {
      if (!this.view) return;
      event.preventDefault();
      const canvas = this.$refs.canvas;
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      const mx = (event.clientX - rect.left) * ratio - canvas.width / 2;
      const my = canvas.height / 2 - (event.clientY - rect.top) * ratio;
      const factor = event.deltaY < 0 ? this.style().zoomStep : 1 / this.style().zoomStep;
      const view = this.view;
      view.x += mx / view.scale - mx / (view.scale * factor);
      view.y += my / view.scale - my / (view.scale * factor);
      view.scale *= factor;
      this.draw();
    },
  },
};
</script>
