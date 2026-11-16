// FHDIC submission deck (HAC-86, v2 HAC-105): keyboard, click and hash navigation over <section class="slide">.
// ←/→, PageUp/PageDown, Space, Home/End move; N toggles the speaker notes; #/<n> deep-links a slide.
// ?export=1 lays every slide out at 1600x900 for the PDF and the video frames (no navigation, no motion).
// v2 motion: staggered reveals (CSS, keyed on .is-current / .is-seen), counters that run up to the value the
// page already carries (.num[data-to]), and the pointer spotlight on .glow cards (ported from 21st GlowCard).
// prefers-reduced-motion turns all of it off; the numbers are then shown as written.
(function () {
  "use strict";
  var root = document.documentElement;
  var params = new URLSearchParams(location.search);
  if (params.get("export") === "1") { root.classList.add("export"); return; }
  root.classList.add("js");

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
  var still = window.matchMedia("(prefers-reduced-motion: reduce)");
  var cur = -1;

  // ---- counters: tween 0 -> data-to (ease-out expo), then leave the exact written value in place
  function countUp(slide) {
    var nums = slide.querySelectorAll(".num[data-to]");
    Array.prototype.forEach.call(nums, function (el) {
      var to = parseFloat(el.getAttribute("data-to"));
      var dec = parseInt(el.getAttribute("data-dec") || "0", 10);
      var final = to.toFixed(dec);
      if (el._raf) cancelAnimationFrame(el._raf);
      if (still.matches || !isFinite(to) || to === 0) { el.textContent = final; return; }
      var t0 = null, dur = 1400, delay = 350;
      el.textContent = (0).toFixed(dec);
      function step(ts) {
        if (t0 === null) t0 = ts + delay;
        var p = Math.min(Math.max((ts - t0) / dur, 0), 1);
        var e = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
        el.textContent = p === 1 ? final : (to * e).toFixed(dec);
        if (p < 1) el._raf = requestAnimationFrame(step);
      }
      el._raf = requestAnimationFrame(step);
    });
  }

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
    if (!phone.matches) countUp(s);
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

  // ---- pointer spotlight: every .glow card on the current slide gets the pointer in its own coordinates,
  // so the edge light spills across neighbouring cards (the GlowCard effect, without fixed attachment).
  var px = 0, py = 0, pending = false;
  function paint() {
    pending = false;
    var s = slides[cur];
    if (!s) return;
    var xp = (px / window.innerWidth).toFixed(3);
    Array.prototype.forEach.call(s.querySelectorAll(".glow"), function (c) {
      var r = c.getBoundingClientRect();
      c.style.setProperty("--x", (px - r.left).toFixed(1) + "px");
      c.style.setProperty("--y", (py - r.top).toFixed(1) + "px");
      c.style.setProperty("--xp", xp);
    });
  }
  document.addEventListener("pointermove", function (e) {
    if (still.matches || e.pointerType === "touch") return;
    px = e.clientX; py = e.clientY;
    if (!pending) { pending = true; requestAnimationFrame(paint); }
  }, { passive: true });

  // Phone width: all slides are on the page; keep the counter and tabs in step with scrolling,
  // and reveal (and count up) each slide the first time it scrolls into view.
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      if (!phone.matches) return;
      es.forEach(function (en) { if (en.isIntersecting) show(slides.indexOf(en.target), false); });
    }, { rootMargin: "-40% 0px -55% 0px" });
    var seen = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting || !phone.matches || en.target.classList.contains("is-seen")) return;
        en.target.classList.add("is-seen");
        countUp(en.target);
      });
    }, { threshold: 0.12 });
    slides.forEach(function (s) { io.observe(s); seen.observe(s); });
  } else {
    slides.forEach(function (s) { s.classList.add("is-seen"); });
  }
  show(fromHash(), false);
})();
