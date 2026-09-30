(function () {
  "use strict";

  const OUTCOME_LABELS = {
    exact_repair: "Exact repair",
    improved: "Improved",
    no_edit: "No edit",
    wrong_position: "Wrong position",
    worse: "Worse",
  };

  const EDIT_LABELS = {
    insert: "Insert",
    delete: "Delete",
    substitute: "Substitute",
    none: "None",
  };

  const MODE_LABELS = {
    teacher_forced: "Teacher forced",
    free_generation: "Free generation",
  };

  function siteRootUrl() {
    const script = document.querySelector('script[src*="gallery.js"]');
    if (script?.src) {
      return new URL("../", script.src);
    }
    return new URL("./", window.location.href);
  }

  function assetUrl(relPath) {
    return new URL(relPath, siteRootUrl()).href;
  }

  let allItems = [];
  let manifestError = false;
  let currentMode = "free_generation";
  let currentEdit = "all";
  let currentOutcome = "all";
  let currentPage = 1;
  const perPage = 12;

  function getFiltered() {
    return allItems.filter((item) => {
      if (item.mode !== currentMode) return false;
      if (currentEdit !== "all" && item.edit_type !== currentEdit) return false;
      if (currentOutcome !== "all" && item.outcome !== currentOutcome) return false;
      return true;
    });
  }

  function setActiveFilter(group, value) {
    document.querySelectorAll('[data-filter-group="' + group + '"]').forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-filter-value") === value);
    });
  }

  function loadGalleryPage() {
    const grid = document.getElementById("main-gallery-grid");
    const empty = document.getElementById("gallery-empty");
    if (!grid) return;

    const filtered = getFiltered();
    const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    grid.innerHTML = "";

    if (filtered.length === 0) {
      if (empty) {
        empty.style.display = "block";
        empty.textContent = manifestError
          ? "Could not load the gallery manifest. Open this page as …/index.html (not the folder URL alone), then hard refresh."
          : allItems.length === 0
            ? "No GIFs in the manifest yet."
            : "No GIFs match the current filters.";
      }
      updatePagination(0, 0);
      return;
    }

    if (empty) empty.style.display = "none";

    const start = (currentPage - 1) * perPage;
    const slice = filtered.slice(start, start + perPage);

    slice.forEach((item) => {
      const card = document.createElement("div");
      card.className = "image-card";

      const img = document.createElement("img");
      img.src = assetUrl(item.path);
      img.alt = item.caption || item.path;
      img.loading = "lazy";
      img.addEventListener("click", () => openLightbox(item));

      const meta = document.createElement("div");
      meta.className = "card-meta";
      meta.innerHTML =
        '<span class="outcome-badge">' +
        (OUTCOME_LABELS[item.outcome] || item.outcome) +
        "</span>" +
        (EDIT_LABELS[item.edit_type] || item.edit_type);

      card.appendChild(img);
      card.appendChild(meta);
      grid.appendChild(card);
    });

    updatePagination(filtered.length, totalPages);
  }

  function updatePagination(total, totalPages) {
    const pageInfo = document.getElementById("main-page-info");
    if (pageInfo) {
      pageInfo.textContent =
        total === 0
          ? "No GIFs yet"
          : "Page " + currentPage + " of " + totalPages + " (" + total + " items)";
    }
    const prev = document.getElementById("gallery-prev");
    const next = document.getElementById("gallery-next");
    if (prev) prev.disabled = currentPage <= 1 || total === 0;
    if (next) next.disabled = currentPage >= totalPages || total === 0;
  }

  function openLightbox(item) {
    const lightbox = document.getElementById("lightbox");
    const img = document.getElementById("lightbox-image");
    const info = document.getElementById("lightbox-info");
    if (!lightbox || !img) return;
    img.src = assetUrl(item.path);
    img.alt = item.caption || "";
    if (info) {
      info.textContent =
        (MODE_LABELS[item.mode] || item.mode) +
        " · " +
        (EDIT_LABELS[item.edit_type] || item.edit_type) +
        " · " +
        (OUTCOME_LABELS[item.outcome] || item.outcome) +
        (item.caption ? " — " + item.caption : "");
    }
    lightbox.classList.add("show");
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    const lightbox = document.getElementById("lightbox");
    if (!lightbox) return;
    lightbox.classList.remove("show");
    document.body.style.overflow = "";
  }

  function bindFilters() {
    document.querySelectorAll("[data-filter-group]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const group = btn.getAttribute("data-filter-group");
        const value = btn.getAttribute("data-filter-value");
        if (group === "mode") currentMode = value;
        if (group === "edit") currentEdit = value;
        if (group === "outcome") currentOutcome = value;
        setActiveFilter(group, value);
        currentPage = 1;
        loadGalleryPage();
      });
    });

    document.getElementById("gallery-prev")?.addEventListener("click", () => {
      currentPage -= 1;
      loadGalleryPage();
    });
    document.getElementById("gallery-next")?.addEventListener("click", () => {
      currentPage += 1;
      loadGalleryPage();
    });

    document.getElementById("lightbox")?.addEventListener("click", closeLightbox);
    document.querySelector(".lightbox-close")?.addEventListener("click", closeLightbox);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeLightbox();
    });
  }

  function applyHashFilters() {
    const hash = window.location.hash.replace(/^#/, "");
    if (!hash) return;
    const params = new URLSearchParams(hash);
    const outcome = params.get("outcome");
    if (outcome && OUTCOME_LABELS[outcome]) {
      currentOutcome = outcome;
      setActiveFilter("outcome", outcome);
    }
  }

  function applyManifest(data) {
    manifestError = false;
    allItems = data && Array.isArray(data.items) ? data.items : [];
    loadGalleryPage();
  }

  function init() {
    bindFilters();
    applyHashFilters();

    if (window.GALLERY_MANIFEST && Array.isArray(window.GALLERY_MANIFEST.items)) {
      applyManifest(window.GALLERY_MANIFEST);
      return;
    }

    fetch(assetUrl("assets/gallery/manifest.json"))
      .then((r) => {
        if (!r.ok) throw new Error("manifest HTTP " + r.status);
        return r.json();
      })
      .then((data) => applyManifest(data))
      .catch((err) => {
        manifestError = true;
        console.warn("Gallery manifest load failed:", err);
        allItems = [];
        loadGalleryPage();
      });
  }

  window.galleryJumpToOutcome = function (outcome) {
    currentOutcome = outcome;
    setActiveFilter("outcome", outcome);
    currentPage = 1;
    loadGalleryPage();
    const el = document.getElementById("gallery");
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
