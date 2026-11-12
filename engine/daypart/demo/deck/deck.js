// FHDIC submission deck (HAC-86): keyboard, click and hash navigation over <section class="slide">.
// ←/→, PageUp/PageDown, Space, Home/End move; N toggles the speaker notes; #/<n> deep-links a slide.
// ?export=1 lays every slide out at 1600x900 for the PDF and the video frames (no navigation).
(function () {
  "use strict";
  var root = document.documentElement;
  var params = new URLSearchParams(location.search);
  if (params.get("export") === "1") { root.classList.add("export"); return; }

  var slides = Array.prototype.slice.call(document.querySelectorAll(".slide"));
  var n = slides.length;
  var prev = document.getElementById("prev");
  var next = document.getElementById("next");
  var count = document.getElementById("count");
  var bar = document.getElementById("progress");
  var notes = document.getElementById("notes-panel");
  var notesBody = document.getElementById("notes-body");
  var notesBtn = document.getElementById("notes-btn");
  var live = document.getElementById("live");
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".sections a"));
  var phone = window.matchMedia("(max-width: 760px)");
  var cur = -1;

  function fromHash() {
    var m = /^#\/(\d+)$/.exec(location.hash);
    var i = m ? parseInt(m[1], 10) - 1 : 0;
    return Math.min(Math.max(i, 0), n - 1);
  }

  function show(i, focus) {
    i = Math.min(Math.max(i, 0), n - 1);
    if (i === cur) return;
    cur = i;
    slides.forEach(function (s, k) {
      s.classList.toggle("is-current", k === i);
      s.classList.toggle("is-past", k < i);
      if (phone.matches) { s.removeAttribute("aria-hidden"); s.inert = false; }
      else { s.setAttribute("aria-hidden", k === i ? "false" : "true"); s.inert = k !== i; }
    });
    var s = slides[i];
    prev.disabled = i === 0;
    next.disabled = i === n - 1;
    count.textContent = (i + 1) + " / " + n;
    bar.style.width = ((i + 1) / n * 100) + "%";
    var sec = s.getAttribute("data-section");
    tabs.forEach(function (t) { t.setAttribute("aria-current", t.getAttribute("data-section") === sec ? "true" : "false"); });
    var nt = s.querySelector(".notes");
    notesBody.innerHTML = nt ? nt.innerHTML : "";
    var want = "#/" + (i + 1);
    if (location.hash !== want) history.replaceState(null, "", want);
    var h = s.querySelector("h1, h2");
    if (live && !phone.matches) live.textContent = "Slide " + (i + 1) + " of " + n + ": " + (h ? h.textContent : "");
    if (phone.matches && focus) s.scrollIntoView({ block: "start" });
    else if (focus && h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
  }

  function go(d) { show(cur + d, false); }

  prev.addEventListener("click", function () { go(-1); });
  next.addEventListener("click", function () { go(1); });
  tabs.forEach(function (t) {
    t.addEventListener("click", function (e) {
      e.preventDefault();
      cur = -1;
      show(parseInt(t.getAttribute("data-to"), 10) - 1, true);
    });
  });
  notesBtn.addEventListener("click", function () {
    notes.hidden = !notes.hidden;
    notesBtn.setAttribute("aria-expanded", notes.hidden ? "false" : "true");
  });
  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
    var k = e.key;
    if (k === "ArrowRight" || k === "PageDown" || (k === " " && !e.shiftKey && t.tagName !== "BUTTON" && t.tagName !== "A")) { e.preventDefault(); go(1); }
    else if (k === "ArrowLeft" || k === "PageUp" || (k === " " && e.shiftKey)) { e.preventDefault(); go(-1); }
    else if (k === "Home") { e.preventDefault(); show(0, false); }
    else if (k === "End") { e.preventDefault(); show(n - 1, false); }
    else if (k === "n" || k === "N") { notesBtn.click(); }
  });
  // Click on the slide body advances; links and buttons keep their own behaviour.
  document.getElementById("stage").addEventListener("click", function (e) {
    if (phone.matches || e.target.closest("a, button")) return;
    var r = slides[cur].getBoundingClientRect();
    go(e.clientX < r.left + r.width / 3 ? -1 : 1);
  });
  window.addEventListener("hashchange", function () { show(fromHash(), true); });
  phone.addEventListener("change", function () { var i = cur; cur = -1; show(i, false); });
  // Phone width: all slides are on the page; keep the counter and tabs in step with scrolling.
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      if (!phone.matches) return;
      es.forEach(function (en) { if (en.isIntersecting) show(slides.indexOf(en.target), false); });
    }, { rootMargin: "-40% 0px -55% 0px" });
    slides.forEach(function (s) { io.observe(s); });
  }
  show(fromHash(), false);
})();
