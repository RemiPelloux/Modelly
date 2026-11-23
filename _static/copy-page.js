// "Copy page" and "View as Markdown" under each page's title. Every page of the site has a
// Markdown copy next to it (decide.html, decide.md), written at build time for pasting into
// a language model; the buttons fetch it. The home page, a landing page, has none.
"use strict";

(function () {
  function markdownUrl() {
    const path = location.pathname;
    return path.endsWith("/") ? path + "index.md" : path.replace(/\.html$/, ".md");
  }

  function button(label, title) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ml-copy-page__btn";
    b.textContent = label;
    b.title = title;
    return b;
  }

  async function copy(btn, status) {
    try {
      const response = await fetch(markdownUrl());
      if (!response.ok) throw new Error(response.status);
      await navigator.clipboard.writeText(await response.text());
      btn.textContent = "Copied";
      status.textContent = "The page is on your clipboard as Markdown.";
    } catch (error) {
      btn.textContent = "Copy failed";
      status.textContent = "The page could not be copied: open it as Markdown and copy from there.";
    }
    setTimeout(() => { btn.textContent = "Copy page"; }, 2000);
  }

  function start() {
    const article = document.querySelector("article.bd-article");
    const title = article && article.querySelector("h1");
    if (!title || document.querySelector(".ml-landing") || location.protocol === "file:") return;
    const bar = document.createElement("div"), status = document.createElement("span");
    bar.className = "ml-copy-page";
    status.className = "ml-copy-page__status";
    status.setAttribute("role", "status");
    const copyBtn = button("Copy page", "Copy this page as Markdown, to paste into an AI assistant");
    const view = document.createElement("a");
    view.className = "ml-copy-page__btn";
    view.href = markdownUrl();
    view.textContent = "View as Markdown";
    copyBtn.addEventListener("click", () => copy(copyBtn, status));
    bar.append(copyBtn, view, status);
    title.after(bar);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
