// Accessibility (WCAG 2.2 AA): the sidebar's expand toggles are <summary> elements with an
// icon only; give each an accessible name from the page it opens.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("details > summary").forEach(function (summary) {
    if (summary.textContent.trim() || summary.getAttribute("aria-label")) return;
    var item = summary.closest("li");
    var link = item && item.querySelector("a");
    var name = link ? link.textContent.trim() : "this section";
    summary.setAttribute("aria-label", "Show the pages under " + name);
  });
});
