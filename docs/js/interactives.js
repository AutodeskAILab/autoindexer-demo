(function () {
  "use strict";

  function makeTokenEl(tok) {
    const el = document.createElement("span");
    el.className = "token " + (tok.type || "normal");
    el.textContent = tok.text;
    return el;
  }

  function renderStream(containerId, tokens) {
    const c = document.getElementById(containerId);
    if (!c) return;
    c.innerHTML = "";
    (tokens || []).forEach((tok) => c.appendChild(makeTokenEl(tok)));
  }

  function makePin(label, kind) {
    const el = document.createElement("span");
    el.className = "cursor-pin " + kind;
    el.textContent = label;
    return el;
  }

  function makeCaret() {
    const el = document.createElement("span");
    el.className = "demo-caret";
    el.setAttribute("aria-hidden", "true");
    el.title = "Edit cursor";
    return el;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  const ROPE_STD = "Standard RoPE";
  const ROPE_K = "Cursor-anchored (key-only) RoPE";

  function editCursorBoundaryDisp(step, sortedByDisp) {
    if (step.cursorAfterDisp !== undefined) {
      return step.cursorAfterDisp;
    }
    if (step.cursorAtGen != null) {
      const anchor = sortedByDisp.find((t) => t.gen === step.cursorAtGen);
      if (anchor) {
        return anchor.disp - 1;
      }
    }
    return null;
  }

  function withEditRope(step) {
    const tokens = (step.laneTokens || []).map((t) => ({ ...t }));
    if (!step.cursors) {
      tokens.forEach((t) => {
        t.rope = ROPE_STD;
      });
      return tokens;
    }
    const sorted = tokens.slice().sort((a, b) => a.disp - b.disp);
    const boundary = editCursorBoundaryDisp(step, sorted);
    tokens.forEach((t) => {
      if (boundary === null) {
        t.rope = ROPE_STD;
      } else {
        t.rope = t.disp > boundary ? ROPE_K : ROPE_STD;
      }
    });
    return tokens;
  }

  function sortedLaneTokens(step) {
    return withEditRope(step).slice().sort((a, b) => a.disp - b.disp);
  }

  function renderDisplayLane(step) {
    const lane = document.getElementById("inference-display-lane");
    if (!lane) return;
    lane.innerHTML = "";

    const tokens = sortedLaneTokens(step);
    const c = step.cursors;
    const cursorAtGen = step.cursorAtGen;
    const cursorAfterDisp = step.cursorAfterDisp;
    const cursorAtEnd = step.cursorAtEnd;

    const pinGen = step.pinGen != null ? step.pinGen : c && c.start;
    const pinsAfterDisp = step.pinsAfterDisp;

    function renderHeadMarkers(streamGen) {
      if (c && c.start === streamGen) {
        lane.appendChild(makePin("start S=" + c.start, "start"));
      }
      if (c && c.end === streamGen) {
        lane.appendChild(makePin("end E=" + c.end, "end"));
      }
      if (cursorAfterDisp === undefined && cursorAtGen === streamGen) {
        lane.appendChild(makeCaret());
      }
    }

    function renderPinCluster() {
      if (pinGen == null) return;
      renderHeadMarkers(pinGen);
    }

    tokens.forEach((row, idx) => {
      if (pinsAfterDisp === undefined) {
        renderHeadMarkers(row.gen);
      } else if (idx === 0 && c && c.start != null && c.start === row.gen) {
        renderHeadMarkers(c.start);
      }
      const wrap = document.createElement("span");
      wrap.className = "disp-token-wrap";
      const tok = document.createElement("span");
      tok.className = "disp-token";
      if (row.inSpan) {
        tok.classList.add("in-span");
      }
      if (row.tokenClass) {
        tok.classList.add(row.tokenClass);
      }
      tok.textContent = row.text;
      wrap.appendChild(tok);
      if (showPositions) {
        const idx = document.createElement("span");
        idx.className = "disp-index";
        idx.textContent = "g" + row.gen;
        wrap.appendChild(idx);
      }
      lane.appendChild(wrap);

      if (pinsAfterDisp !== undefined && row.disp === pinsAfterDisp) {
        renderPinCluster();
      }
      if (cursorAfterDisp !== undefined && row.disp === cursorAfterDisp) {
        lane.appendChild(makeCaret());
      }
    });

    if (cursorAtEnd) {
      lane.appendChild(makeCaret());
    }
  }

  function renderPositionPanel(step) {
    const content = document.getElementById("inference-pos-content");
    const ropeEl = document.getElementById("inference-rope-note");
    if (!content) return;

    const rows = sortedLaneTokens(step);
    if (!rows.length) {
      content.innerHTML = "<p class=\"demo-note\">No visible vocabulary tokens in this step.</p>";
      if (ropeEl) ropeEl.textContent = step.ropeNote || "";
      return;
    }

    let html =
      '<div class="pos-table-wrap"><table class="pos-table"><thead><tr>' +
      "<th>Token</th><th>Generation order</th><th>Display order</th><th>RoPE type</th>" +
      "</tr></thead><tbody>";
    rows.forEach((row) => {
      html +=
        "<tr><td>" +
        escapeHtml(row.text) +
        "</td><td>" +
        row.gen +
        "</td><td>" +
        row.disp +
        "</td><td>" +
        escapeHtml(row.rope || "—") +
        "</td></tr>";
    });
    html += "</tbody></table></div>";
    if (step.positionNote) {
      html += "<p class=\"demo-note\">" + escapeHtml(step.positionNote) + "</p>";
    }
    content.innerHTML = html;
    if (ropeEl) {
      ropeEl.textContent =
        step.ropeNote ||
        (step.cursors
          ? "During an edit: tokens before the cursor in display order use standard RoPE; tokens after the cursor use cursor-anchored (key-only) RoPE on keys."
          : "");
    }
  }

  function laneAtC(disp) {
    return { text: "@", gen: 0, disp: disp };
  }
  function laneDollar(disp, opts) {
    const inserted = !(opts && opts.plain);
    return {
      text: "$",
      gen: 3,
      disp: disp,
      tokenClass: inserted ? "inserted" : null,
    };
  }
  function laneB(disp, opts) {
    const inserted = !(opts && opts.plain);
    return {
      text: "B",
      gen: 4,
      disp: disp,
      tokenClass: inserted ? "inserted" : null,
    };
  }
  function laneC(disp) {
    return { text: "C", gen: 1, disp: disp };
  }
  function laneD(disp) {
    return { text: "D", gen: 6, disp: disp };
  }

  // Start + 11 generation steps (Figure 1 style tokens).
  const inferenceSteps = [
    {
      title: "Start",
      laneTokens: [laneAtC(0), laneC(1)],
      gen: [{ text: "@", type: "normal" }, { text: "C", type: "normal" }],
      cursorAtGen: null,
      cursorAtEnd: true,
      cursors: null,
      note: "Visible layout @ C. Generation-order indices 0 and 1 are what the cursor head uses.",
      positionNote: null,
      ropeNote: null,
    },
    {
      title: "1. Generate [EDIT]; start cursor S = 1",
      laneTokens: [laneAtC(0), laneC(1)],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
      ],
      cursorAtGen: 1,
      cursors: { start: 1, end: null },
      note:
        "[EDIT] and start S are predicted together. S = 1 is the generation-order index immediately before C.",
      positionNote: "S = 1 (generation order). End E not yet sampled.",
      ropeNote: null,
    },
    {
      title: "2. End cursor E = 1; cursor between @ and C",
      laneTokens: [laneAtC(0), laneC(1)],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
      ],
      cursorAtGen: 1,
      cursors: { start: 1, end: 1 },
      note:
        "Insertion edit: S = E = 1. The span is empty; the blinking cursor sits at generation-order index 1 (between @ and C).",
      positionNote: "Span (S, E) = (1, 1) in generation-order indices.",
      ropeNote:
        "During an edit: tokens before the cursor in display order use standard RoPE; tokens at or after the cursor use cursor-anchored (key-only) RoPE on keys.",
    },
    {
      title: "3. Generate $ (display at cursor; stream appends)",
      laneTokens: [
        laneAtC(0),
        laneDollar(1),
        laneC(2),
      ],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
      ],
      cursors: { start: 1, end: 1 },
      pinsAfterDisp: 0,
      pinGen: 1,
      cursorAfterDisp: 1,
      note:
        "$ is inserted at the edit cursor in the layout (@ $ C), while the append stream grows after [EDIT].",
      positionNote: "$ has generation-order index 3 in the stream; display order 1 in the layout.",
      ropeNote: null,
    },
    {
      title: "4. Generate B",
      laneTokens: [laneAtC(0), laneDollar(1), laneB(2), laneC(3)],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
      ],
      cursors: { start: 1, end: 1 },
      pinsAfterDisp: 0,
      pinGen: 1,
      cursorAfterDisp: 2,
      note: "B appends in the stream and follows $ at the in-edit cursor in the layout (@ $ B C).",
      positionNote: null,
      ropeNote: null,
    },
    {
      title: "5. RETURN: clear highlight, mask span tokens, cursor to end",
      laneTokens: [laneAtC(0), laneDollar(1), laneB(2), laneC(3)],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
      ],
      cursorAtEnd: true,
      cursors: null,
      pinsAfterDisp: 0,
      pinGen: 1,
      note:
        "[RETURN] ends the edit block. Layout stays @ $ B C with no parser reordering; cursor moves to the end.",
      positionNote: null,
      ropeNote: null,
    },
    {
      title: "6. Generate D",
      laneTokens: [
        laneAtC(0),
        laneDollar(1, { plain: true }),
        laneB(2, { plain: true }),
        laneC(3),
        laneD(4),
      ],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
        { text: "D", type: "normal" },
      ],
      cursorAtEnd: true,
      cursors: null,
      note: "Normal continuation: D appends as generation-order index 6 in the stream (layout @ $ B C D).",
      positionNote: "D display order 4; generation-order index 6 in the append stream.",
      ropeNote: null,
    },
    {
      title: "7. [EDIT] with start S = 0",
      laneTokens: [
        laneAtC(0),
        laneDollar(1, { plain: true }),
        laneB(2, { plain: true }),
        laneC(3),
        laneD(4),
      ],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
        { text: "D", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
      ],
      cursorAtGen: 0,
      cursors: { start: 0, end: null },
      note:
        "Second edit on layout @ $ B C D. Cursor indices remain generation-order stream positions, not display slots.",
      positionNote: "S = 0 before @ (generation order). Display orders 0…4 unchanged.",
      ropeNote: null,
    },
    {
      title: "8. End E = 4 (before B); highlight @ and $ only",
      laneTokens: [
        Object.assign(laneAtC(0), { inSpan: true }),
        Object.assign(laneDollar(1, { plain: true }), { inSpan: true }),
        laneB(2, { plain: true }),
        laneC(3),
        laneD(4),
      ],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
        { text: "D", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
      ],
      cursorAtGen: 4,
      cursors: { start: 0, end: 4 },
      note:
        "E = 4 is the generation-order index immediately before B (not display index 2). Only @ and $ lie in the active span.",
      positionNote:
        "Span (S, E) = (0, 4) in generation order. Highlighted vocab: @ (0) and $ (3).",
      ropeNote: null,
    },
    {
      title: "10. Generate A in layout (after end cursor; @ and $ still visible)",
      laneTokens: [
        Object.assign(laneAtC(0), { inSpan: true }),
        Object.assign(laneDollar(1, { plain: true }), { inSpan: true }),
        { text: "A", gen: 8, disp: 2, tokenClass: "inserted" },
        laneB(3, { plain: true }),
        laneC(4),
        laneD(5),
      ],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
        { text: "D", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "A", type: "inserted" },
      ],
      cursors: { start: 0, end: 4 },
      pinsAfterDisp: 1,
      pinGen: 4,
      cursorAfterDisp: 2,
      note:
        "Start/end pins stay at generation-order S = 0 and E = 4. A is placed after the end marker; @ and $ remain in the row until [RETURN].",
      positionNote: "Display order: @, $, then pins, then A, then B C D.",
      ropeNote: null,
    },
    {
      title: "11. [RETURN]",
      laneTokens: [
        { text: "A", gen: 8, disp: 0 },
        { text: "B", gen: 4, disp: 1 },
        { text: "C", gen: 1, disp: 2 },
        { text: "D", gen: 6, disp: 3 },
      ],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
        { text: "D", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "A", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
      ],
      cursorAtEnd: true,
      cursors: null,
      note: "Second edit closes; masked span tokens (@, $) are dropped from attention and the layout compacts to A B C D.",
      positionNote: null,
      ropeNote: null,
    },
    {
      title: "11. Generate E",
      laneTokens: [
        { text: "A", gen: 8, disp: 0 },
        { text: "B", gen: 4, disp: 1 },
        { text: "C", gen: 1, disp: 2 },
        { text: "D", gen: 6, disp: 3 },
        { text: "E", gen: 10, disp: 4 },
      ],
      gen: [
        { text: "@", type: "normal" },
        { text: "C", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "$", type: "inserted" },
        { text: "B", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
        { text: "D", type: "normal" },
        { text: "[EDIT]", type: "edit-marker" },
        { text: "A", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
        { text: "E", type: "normal" },
      ],
      cursorAtEnd: true,
      cursors: null,
      note: "E appends at generation-order index 10 in the stream (display order 4).",
      positionNote: null,
      ropeNote: null,
    },
  ];

  let inferenceIndex = 0;
  let inferenceTimer = null;
  let showPositions = false;

  function renderInferenceStep() {
    const step = inferenceSteps[inferenceIndex];
    document.getElementById("inference-step-title").textContent = step.title;
    document.getElementById("inference-note").textContent = step.note;

    renderDisplayLane(step);
    renderPositionPanel(step);

    document.getElementById("inference-gen-label").style.display = "";
    document.getElementById("inference-gen-stream").style.display = "";
    renderStream("inference-gen-stream", step.gen || []);

    document.getElementById("inference-counter").textContent =
      "Step " + (inferenceIndex + 1) + " / " + inferenceSteps.length;

    document.getElementById("inference-prev").disabled = inferenceIndex === 0;
    document.getElementById("inference-next").disabled =
      inferenceIndex === inferenceSteps.length - 1;
  }

  function stopInferencePlay() {
    if (inferenceTimer) {
      clearInterval(inferenceTimer);
      inferenceTimer = null;
    }
    document.getElementById("inference-play").textContent = "Play";
  }

  function playInference() {
    if (inferenceTimer) {
      stopInferencePlay();
      return;
    }
    inferenceIndex = 0;
    renderInferenceStep();
    document.getElementById("inference-play").textContent = "Pause";
    inferenceTimer = setInterval(() => {
      if (inferenceIndex >= inferenceSteps.length - 1) {
        stopInferencePlay();
        return;
      }
      inferenceIndex += 1;
      renderInferenceStep();
    }, 2200);
  }

  const trainingScenarios = {
    insert: {
      ground:
        '<h4 className="… contact-titles">Do you have a question or are you a hairstylist looking to join us?</h4>',
      corrupted:
        '<h4 className="… contact-t <<<…>>> question or are you a hairstylist looking to join us?</h4>',
      trajectory: [
        { text: "[EDIT]", type: "edit-marker" },
        { text: "itles\">Do you have a", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
      ],
      cursors: "Insertion: S = E before the missing span (paper example: start=61, end=61).",
      supervision:
        "Perturbation removes text; τ undoes the inverse edit. Supervise markers, cursor (S,E), and token targets in τ.",
    },
    delete: {
      ground: 'op.add<…>("", "mask", "mask image path", "");',
      corrupted: 'op.add<…>("", "mask", "mask image <<<garbage tokens>>> path", "");',
      trajectory: [
        { text: "[EDIT]", type: "edit-marker" },
        { text: "[RETURN]", type: "return-marker" },
      ],
      cursors: "Deletion: S < E with no replacement tokens between markers (span covers noise).",
      supervision: "Target trajectory teaches the model to remove the injected span.",
    },
    substitute: {
      ground: "import org.netbeans.modules.lsp.client.LSPBindings; …",
      corrupted: "import org.netbeans <<<noise>>> .client.LSPBindings; …",
      trajectory: [
        { text: "[EDIT]", type: "edit-marker" },
        { text: ".modules.lsp", type: "inserted" },
        { text: "[RETURN]", type: "return-marker" },
      ],
      cursors: "Substitution: S < E over corrupted tokens; replacements emitted before [RETURN].",
      supervision: "τ is built by undoing sampled inverse edits from clean x (Eq. 1).",
    },
    none: {
      ground: "{ 1, 2 } >= { 1, 2 } true Every set is a superset of itself.",
      corrupted: "{ 1, 2 } >= { 1, 2 } true Every set is a superset of itself.",
      trajectory: [{ text: "(no [EDIT] in τ)", type: "normal" }],
      cursors: "No perturbation on this window: ordinary causal tokens only.",
      supervision: "89/100 no-edit drafts in free generation abstain correctly (paper Table).",
    },
  };

  let trainingKey = "substitute";

  function renderCorruptedSentence(scenario) {
    const el = document.getElementById("training-corrupted");
    if (!el) return;
    el.innerHTML = "";
    const text = scenario.corrupted;
    const re = /<<<([^>]*)>>>/g;
    let last = 0;
    let match;
    while ((match = re.exec(text)) !== null) {
      if (match.index > last) {
        el.appendChild(document.createTextNode(text.slice(last, match.index)));
      }
      const span = document.createElement("span");
      span.style.background = "var(--accent-muted)";
      span.style.borderRadius = "3px";
      span.style.padding = "0 2px";
      span.textContent = match[1] || "…";
      el.appendChild(span);
      last = match.index + match[0].length;
    }
    if (last < text.length) {
      el.appendChild(document.createTextNode(text.slice(last)));
    }
  }

  function renderTraining() {
    const scenario = trainingScenarios[trainingKey];
    document.getElementById("training-ground").textContent = scenario.ground;
    renderCorruptedSentence(scenario);
    renderStream("training-trajectory", scenario.trajectory);
    document.getElementById("training-cursors").textContent = scenario.cursors;
    document.getElementById("training-supervision").textContent = scenario.supervision;
  }

  function initTabs() {
    document.querySelectorAll(".demo-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        const target = tab.getAttribute("data-panel");
        document.querySelectorAll(".demo-tab").forEach((t) => t.classList.remove("active"));
        document.querySelectorAll(".demo-panel").forEach((p) => p.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById(target)?.classList.add("active");
      });
    });
  }

  function initInference() {
    document.getElementById("inference-play")?.addEventListener("click", playInference);
    document.getElementById("inference-prev")?.addEventListener("click", () => {
      stopInferencePlay();
      inferenceIndex = Math.max(0, inferenceIndex - 1);
      renderInferenceStep();
    });
    document.getElementById("inference-next")?.addEventListener("click", () => {
      stopInferencePlay();
      inferenceIndex = Math.min(inferenceSteps.length - 1, inferenceIndex + 1);
      renderInferenceStep();
    });
    document.getElementById("inference-reset")?.addEventListener("click", () => {
      stopInferencePlay();
      inferenceIndex = 0;
      renderInferenceStep();
    });
    document.getElementById("show-positions")?.addEventListener("change", (e) => {
      showPositions = e.target.checked;
      renderInferenceStep();
    });
    renderInferenceStep();
  }

  function initTraining() {
    document.querySelectorAll(".chip[data-training]").forEach((chip) => {
      chip.addEventListener("click", () => {
        trainingKey = chip.getAttribute("data-training");
        document.querySelectorAll(".chip[data-training]").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        renderTraining();
      });
    });
    renderTraining();
  }

  initTabs();
  initInference();
  initTraining();
})();
