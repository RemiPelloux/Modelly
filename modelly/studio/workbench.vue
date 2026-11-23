<template>
  <div class="mx-workbench">
    <div
      v-show="panel"
      class="mx-resizer"
      role="separator"
      tabindex="0"
      aria-orientation="vertical"
      :aria-label="labels['Resize the side panel']"
      ref="handle"
      :aria-valuemin="min_width()"
      @pointerdown="grab"
      @keydown="nudge"
    ></div>
    <div v-if="help" class="mx-help-backdrop" @click.self="close_help">
      <div
        class="mx-help"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mx-help-title"
        @keydown.esc="close_help"
      >
        <h2 id="mx-help-title">{{ labels["Keyboard shortcuts"] }}</h2>
        <table>
          <tr v-for="row in shortcuts" :key="row[0]">
            <td><kbd>{{ row[0] }}</kbd></td>
            <td>{{ row[1] }}</td>
          </tr>
        </table>
        <button ref="close" type="button" class="mx-help-close" @click="close_help">
          {{ labels["Close"] }}
        </button>
      </div>
    </div>
  </div>
</template>
<script>
// Modelly Studio's workbench, browser side: the side panel's resize handle, the page's
// keyboard shortcuts and their help, and what the browser keeps between visits (the open
// panel, the open tab, the panel's width) in local storage. A key typed into a field, a
// slider, the tab strip or a button is left to that control.
module.exports = {
  mounted() {
    const width = Number(this.stored("width", 0));
    if (width) this.apply(width);
    else this.describe(300); // the stylesheet's default width
    const panel = this.stored("panel", null);
    if (panel !== null) this.panel = panel || null;
    const tab = this.stored("tab", null);
    if (tab) this.tab = tab;
    this.listener = (event) => this.shortcut(event);
    window.addEventListener("keydown", this.listener);
  },
  beforeDestroy() {
    window.removeEventListener("keydown", this.listener);
  },
  beforeUnmount() {
    this.$options.beforeDestroy.call(this);
  },
  watch: {
    panel(value) {
      this.keep("panel", value || "");
    },
    tab(value) {
      this.keep("tab", value);
    },
    help(open) {
      if (open) this.$nextTick(() => this.$refs.close && this.$refs.close.focus());
    },
  },
  methods: {
    stored(name, fallback) {
      try {
        const value = window.localStorage.getItem("modelly.studio." + name);
        return value === null ? fallback : value;
      } catch (error) {
        return fallback; // storage blocked: Studio opens with its defaults
      }
    },
    keep(name, value) {
      try {
        window.localStorage.setItem("modelly.studio." + name, String(value));
      } catch (error) {
        // storage blocked or full: nothing is kept, nothing breaks
      }
    },
    apply(width) {
      const clamped = Math.round(Math.min(this.max_width(), Math.max(this.min_width(), width)));
      document.documentElement.style.setProperty("--mx-panel-width", clamped + "px");
      this.describe(clamped);
      return clamped;
    },
    describe(width) {
      // Not reactive data: a drag sends nothing to the server.
      this.width = width;
      this.$refs.handle.setAttribute("aria-valuenow", width);
      this.$refs.handle.setAttribute("aria-valuemax", this.max_width());
    },
    min_width() {
      return 200;
    },
    max_width() {
      return Math.max(this.min_width(), Math.min(640, window.innerWidth - 360));
    },
    open_panel() {
      return document.querySelector(".mx-panel:not(.mx-hidden)");
    },
    rtl() {
      return getComputedStyle(this.$el).direction === "rtl";
    },
    grab(event) {
      const panel = this.open_panel();
      if (!panel || event.button !== 0) return;
      event.preventDefault();
      const handle = event.currentTarget;
      const box = panel.getBoundingClientRect();
      const rtl = this.rtl();
      handle.setPointerCapture(event.pointerId);
      handle.classList.add("is-dragging");
      const move = (moved) => this.apply(rtl ? box.right - moved.clientX : moved.clientX - box.left);
      const drop = () => {
        handle.classList.remove("is-dragging");
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", drop);
        handle.removeEventListener("pointercancel", drop);
        this.keep("width", this.width);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", drop);
      handle.addEventListener("pointercancel", drop);
    },
    nudge(event) {
      const panel = this.open_panel();
      const grow = { ArrowRight: 16, ArrowLeft: -16 }[event.key];
      if (!panel || !grow) return;
      event.preventDefault();
      event.stopPropagation();
      const width = panel.getBoundingClientRect().width + (this.rtl() ? -grow : grow);
      this.keep("width", this.apply(width));
    },
    close_help() {
      this.help = false;
    },
    typing(target) {
      const owned = "input, textarea, select, [contenteditable], [role='slider'], " +
        "[role='separator'], [role='tab'], [role='tablist'], .v-field, .v-slider";
      return Boolean(target && target.closest && target.closest(owned));
    },
    shortcut(event) {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "Escape" && this.help) {
        this.help = false;
        return;
      }
      if (event.key === "?") {
        if (this.typing(event.target)) return;
        event.preventDefault();
        this.help = !this.help;
        return;
      }
      const name = { " ": "play", ArrowRight: "forward", ArrowLeft: "back", End: "live" }[event.key];
      if (!name || this.help || this.typing(event.target)) return;
      // Space on a focused button or link presses that control, as everywhere else.
      if (name === "play" && event.target.closest && event.target.closest("button, a")) return;
      event.preventDefault();
      this.key(name);
    },
  },
};
</script>
