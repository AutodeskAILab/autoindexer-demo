// ─── SLIDE 6B: VANILLA VS AUTOINDEXER TOKEN-STREAM ANIMATION ──────────────
(function () {
  const TYPE_CLASS = {
    normal: "tok-normal",
    inserted: "tok-insert",
    deleted: "tok-delete",
    "edit-marker": "tok-edit",
    "return-marker": "tok-return",
  };

  function makeCmpTokenEl(text, type, pos) {
    const el = document.createElement("span");
    el.className = "token " + (TYPE_CLASS[type] || "tok-normal") + " tok-fade-in";
    // Always render a second "pos" line, even for markers that have none, so
    // every token box shares the same two-line height (see .pos-placeholder).
    const posSpan = pos !== undefined
      ? '<span class="pos">pos=' + pos + "</span>"
      : '<span class="pos pos-placeholder">pos=0</span>';
    el.innerHTML = text + posSpan;
    return el;
  }

  function makeCmpArrow() {
    const el = document.createElement("span");
    el.className = "arrow";
    el.textContent = "\u2192";
    return el;
  }

  // Vanilla decoder: strictly left-to-right, generation pos === display pos.
  const vanillaCmpTokens = [
    { text: "The", pos: 0 },
    { text: "robot", pos: 1 },
    { text: "moved", pos: 2 },
    { text: "item", pos: 3 },
    { text: ".", pos: 4 },
  ];

  // AutoIndexer generation stream: append-only, includes EDIT/RETURN markers.
  // Same trajectory as the sharepoint explainer's Section 4 example.
  const genStreamTokens = [
    { text: "The", type: "normal", pos: 0 },
    { text: "robot", type: "normal", pos: 3 },
    { text: "moved", type: "normal", pos: 5 },
    { text: "item", type: "deleted" },
    { text: ".", type: "normal", pos: 13 },
    { text: "EDIT", type: "edit-marker" },
    { text: "small", type: "inserted", pos: 1 },
    { text: "warehouse", type: "inserted", pos: 2 },
    { text: "RETURN", type: "return-marker" },
    { text: "EDIT", type: "edit-marker" },
    { text: "carefully", type: "inserted", pos: 4 },
    { text: "RETURN", type: "return-marker" },
    { text: "EDIT", type: "edit-marker" },
    { text: "the", type: "inserted", pos: 6 },
    { text: "fragile", type: "inserted", pos: 7 },
    { text: "box", type: "inserted", pos: 8 },
    { text: "to", type: "inserted", pos: 9 },
    { text: "the", type: "inserted", pos: 10 },
    { text: "loading", type: "inserted", pos: 11 },
    { text: "dock", type: "inserted", pos: 12 },
    { text: "RETURN", type: "return-marker" },
  ];

  function revealStream(containerId, tokens, interval, onDone) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    let idx = 0;
    const timer = setInterval(() => {
      if (idx > 0) container.appendChild(makeCmpArrow());
      const t = tokens[idx];
      container.appendChild(makeCmpTokenEl(t.text, t.type, t.pos));
      idx++;
      if (idx >= tokens.length) {
        clearInterval(timer);
        if (onDone) setTimeout(onDone, 500);
      }
    }, interval);
    return timer;
  }

  // Re-renders the display panel from `displayItems` (kept sorted by display
  // position), giving the token at `highlightIdx` a brief insertion pulse so
  // it's easy to spot landing in the middle of the sentence, not just at the
  // end.
  function renderDisplayItems(dispEl, displayItems, highlightIdx) {
    dispEl.innerHTML = "";
    displayItems.forEach((t, i) => {
      const el = makeCmpTokenEl(t.text, t.type, t.pos);
      if (i === highlightIdx) el.classList.add("tok-just-inserted");
      dispEl.appendChild(el);
    });
  }

  // Plays the generation stream token-by-token; every token that carries a
  // display `pos` is inserted into the display panel *at the same step*, in
  // its correct sorted slot (not appended at the end) — so the reconstructed
  // sentence grows in place as decoding happens, mirroring how
  // AutoIndexerIdParser assigns position_ids incrementally during decoding.
  function playAutoIndexerSync(genEl, dispEl, interval, onDone) {
    genEl.innerHTML = "";
    dispEl.innerHTML = "";
    const displayItems = [];
    let idx = 0;

    const timer = setInterval(() => {
      if (idx > 0) genEl.appendChild(makeCmpArrow());
      const t = genStreamTokens[idx];
      genEl.appendChild(makeCmpTokenEl(t.text, t.type, t.pos));

      if (t.pos !== undefined) {
        let insertAt = displayItems.findIndex((d) => d.pos > t.pos);
        if (insertAt === -1) insertAt = displayItems.length;
        displayItems.splice(insertAt, 0, t);
        renderDisplayItems(dispEl, displayItems, insertAt);
      }

      idx++;
      if (idx >= genStreamTokens.length) {
        clearInterval(timer);
        if (onDone) setTimeout(onDone, 500);
      }
    }, interval);
    return timer;
  }

  let vanillaCmpRunning = false;
  let autoindexerCmpRunning = false;

  // Independent play button — just the vanilla decoder panel.
  window.playVanillaCompare = function () {
    if (vanillaCmpRunning) return;
    vanillaCmpRunning = true;
    const btn = document.getElementById("play-vanilla-cmp");
    btn.disabled = true;

    revealStream("vanilla-cmp-stream", vanillaCmpTokens, 550, () => {
      btn.disabled = false;
      btn.textContent = "\u21BA Replay";
      vanillaCmpRunning = false;
    });
  };

  // Independent play button — the AutoIndexer generation + display panels,
  // synchronized as described above.
  window.playAutoIndexerCompare = function () {
    if (autoindexerCmpRunning) return;
    autoindexerCmpRunning = true;
    const btn = document.getElementById("play-autoindexer-cmp");
    const genEl = document.getElementById("ai-gen-stream");
    const dispEl = document.getElementById("ai-display-stream");
    btn.disabled = true;

    playAutoIndexerSync(genEl, dispEl, 480, () => {
      btn.disabled = false;
      btn.textContent = "\u21BA Replay";
      autoindexerCmpRunning = false;
    });
  };
})();

(function () {
  const slides = Array.from(document.querySelectorAll(".slide"));
  const counter = document.getElementById("counter");
  const dotsContainer = document.getElementById("dots");
  const progressFill = document.getElementById("progress-fill");
  const prevBtn = document.getElementById("prev-btn");
  const nextBtn = document.getElementById("next-btn");

  let current = 0;

  slides.forEach((_, i) => {
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.addEventListener("click", () => goTo(i));
    dotsContainer.appendChild(dot);
  });
  const dots = Array.from(dotsContainer.children);

  function render() {
    slides.forEach((s, i) => s.classList.toggle("active", i === current));
    dots.forEach((d, i) => d.classList.toggle("active", i === current));
    counter.textContent = (current + 1) + " / " + slides.length;
    progressFill.style.width = ((current + 1) / slides.length * 100) + "%";
    prevBtn.disabled = current === 0;
    nextBtn.disabled = current === slides.length - 1;
    slides[current].scrollTop = 0;
    history.replaceState(null, "", "#" + (current + 1));
  }

  function goTo(idx) {
    current = Math.max(0, Math.min(slides.length - 1, idx));
    render();
  }

  function next() { goTo(current + 1); }
  function prev() { goTo(current - 1); }

  prevBtn.addEventListener("click", prev);
  nextBtn.addEventListener("click", next);

  document.addEventListener("keydown", (e) => {
    if (["ArrowRight", "PageDown", " "].includes(e.key)) { e.preventDefault(); next(); }
    else if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); prev(); }
    else if (e.key === "Home") { e.preventDefault(); goTo(0); }
    else if (e.key === "End") { e.preventDefault(); goTo(slides.length - 1); }
  });

  // Basic swipe support for touch devices
  let touchStartX = null;
  document.addEventListener("touchstart", (e) => { touchStartX = e.touches[0].clientX; });
  document.addEventListener("touchend", (e) => {
    if (touchStartX === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 60) { dx < 0 ? next() : prev(); }
    touchStartX = null;
  });

  // Deep-link support: #3 opens slide 3
  const hashIdx = parseInt((location.hash || "").replace("#", ""), 10);
  if (!isNaN(hashIdx) && hashIdx >= 1 && hashIdx <= slides.length) {
    current = hashIdx - 1;
  }

  render();
})();
