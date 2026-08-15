/* =========================================================
   Backdrop Buddies — app.js
   A fun, colorful iPad background picker for kids.
   ========================================================= */
(function () {
  "use strict";

  const FAV_KEY = "backdropBuddies.favorites";
  const SOUND_KEY = "backdropBuddies.soundOn";

  const state = {
    all: [],
    categories: [],
    filtered: [],
    activeCategory: "all",
    searchTerm: "",
    favorites: new Set(loadFavorites()),
    soundOn: localStorage.getItem(SOUND_KEY) === "true",
    previewIndex: -1,
    audioCtx: null,
  };

  // ---- DOM refs -----------------------------------------------------
  const el = {
    loadingScreen: document.getElementById("loading-screen"),
    tabs: document.getElementById("tabs"),
    grid: document.getElementById("grid"),
    resultsCount: document.getElementById("results-count"),
    emptyState: document.getElementById("empty-state"),
    searchInput: document.getElementById("search-input"),
    randomBtn: document.getElementById("random-btn"),
    soundToggle: document.getElementById("sound-toggle"),
    soundIcon: document.getElementById("sound-icon"),

    gridView: document.getElementById("grid-view"),
    previewView: document.getElementById("preview-view"),
    previewBack: document.getElementById("preview-back"),
    previewTitle: document.getElementById("preview-title"),
    previewCategory: document.getElementById("preview-category"),
    previewFav: document.getElementById("preview-fav"),
    previewFavIcon: document.getElementById("preview-fav-icon"),
    previewImg: document.getElementById("preview-img"),
    previewFrame: document.getElementById("preview-frame"),
    prevBtn: document.getElementById("prev-btn"),
    nextBtn: document.getElementById("next-btn"),
    setBgBtn: document.getElementById("set-bg-btn"),
    downloadBtn: document.getElementById("download-btn"),
    setToast: document.getElementById("set-toast"),
    confettiWrap: document.getElementById("confetti-canvas-wrap"),
  };

  // ---- Bootstrap ------------------------------------------------------
  fetch("images/backgrounds.json")
    .then((r) => r.json())
    .then((data) => {
      state.all = data.backgrounds;
      state.categories = data.categories;
      buildTabs();
      applyFilters();
      finishLoading();
    })
    .catch((err) => {
      console.error("Failed to load backgrounds.json", err);
      el.resultsCount.textContent = "Oops! Couldn't load backgrounds.";
      finishLoading();
    });

  function finishLoading() {
    setTimeout(() => el.loadingScreen.classList.add("hide"), 350);
  }

  // ---- Favorites --------------------------------------------------------
  function loadFavorites() {
    try {
      return JSON.parse(localStorage.getItem(FAV_KEY)) || [];
    } catch (e) {
      return [];
    }
  }
  function saveFavorites() {
    localStorage.setItem(FAV_KEY, JSON.stringify([...state.favorites]));
  }
  function isFav(id) {
    return state.favorites.has(id);
  }
  function toggleFav(id) {
    if (state.favorites.has(id)) state.favorites.delete(id);
    else state.favorites.add(id);
    saveFavorites();
    updateTabCounts();
  }

  // ---- Tabs ---------------------------------------------------------------
  function buildTabs() {
    const cats = [{ slug: "all", name: "All" }].concat(state.categories);
    el.tabs.innerHTML = "";
    cats.forEach((c) => {
      const btn = document.createElement("button");
      btn.className = "tab-btn" + (c.slug === "all" ? " active" : "");
      btn.type = "button";
      btn.dataset.slug = c.slug;
      btn.innerHTML = `<span>${c.slug === "all" ? "🌈" : ""}${escapeHtml(c.name)}</span><span class="tab-count"></span>`;
      btn.addEventListener("click", () => {
        state.activeCategory = c.slug;
        [...el.tabs.children].forEach((b) => b.classList.toggle("active", b === btn));
        applyFilters();
      });
      el.tabs.appendChild(btn);
    });
    // favorites tab
    const favBtn = document.createElement("button");
    favBtn.className = "tab-btn";
    favBtn.type = "button";
    favBtn.dataset.slug = "favorites";
    favBtn.innerHTML = `<span>💖 Favorites</span><span class="tab-count"></span>`;
    favBtn.addEventListener("click", () => {
      state.activeCategory = "favorites";
      [...el.tabs.children].forEach((b) => b.classList.toggle("active", b === favBtn));
      applyFilters();
    });
    el.tabs.appendChild(favBtn);
    updateTabCounts();
  }

  function updateTabCounts() {
    [...el.tabs.children].forEach((btn) => {
      const slug = btn.dataset.slug;
      const countEl = btn.querySelector(".tab-count");
      let n;
      if (slug === "all") n = state.all.length;
      else if (slug === "favorites") n = state.favorites.size;
      else n = state.all.filter((b) => b.category === slug).length;
      countEl.textContent = `(${n})`;
    });
  }

  // ---- Filtering ------------------------------------------------------------
  el.searchInput.addEventListener("input", debounce(() => {
    state.searchTerm = el.searchInput.value.trim().toLowerCase();
    applyFilters();
  }, 150));

  function applyFilters() {
    let list = state.all;
    if (state.activeCategory === "favorites") {
      list = list.filter((b) => state.favorites.has(b.id));
    } else if (state.activeCategory !== "all") {
      list = list.filter((b) => b.category === state.activeCategory);
    }
    if (state.searchTerm) {
      const t = state.searchTerm;
      list = list.filter((b) =>
        b.title.toLowerCase().includes(t) ||
        b.categoryName.toLowerCase().includes(t) ||
        (b.tags || []).some((tag) => tag.toLowerCase().includes(t))
      );
    }
    state.filtered = list;
    renderGrid();
  }

  // ---- Grid rendering with lazy loading -----------------------------------
  let observer;
  function renderGrid() {
    el.grid.innerHTML = "";
    el.resultsCount.textContent = state.filtered.length
      ? `${state.filtered.length} background${state.filtered.length === 1 ? "" : "s"}`
      : "";
    el.emptyState.hidden = state.filtered.length !== 0;

    if (observer) observer.disconnect();
    observer = new IntersectionObserver(onIntersect, { rootMargin: "300px 0px" });

    const frag = document.createDocumentFragment();
    state.filtered.forEach((bg, i) => {
      frag.appendChild(buildCard(bg, i));
    });
    el.grid.appendChild(frag);
  }

  function buildCard(bg, index) {
    const card = document.createElement("div");
    card.className = "card loading";
    card.setAttribute("role", "listitem");
    card.tabIndex = 0;
    card.dataset.id = bg.id;
    card.style.animationDelay = Math.min(index * 18, 400) + "ms";
    if (isFav(bg.id)) card.classList.add("is-favorited");

    const img = document.createElement("img");
    img.dataset.src = bg.filename;
    img.alt = bg.title + " — " + bg.categoryName + " iPad background";
    img.loading = "lazy";

    const overlay = document.createElement("div");
    overlay.className = "card-overlay";
    overlay.innerHTML = `<p class="card-title">${escapeHtml(bg.title)}</p><p class="card-cat">${escapeHtml(bg.categoryName)}</p>`;

    const favBtn = document.createElement("button");
    favBtn.className = "fav-btn";
    favBtn.type = "button";
    favBtn.setAttribute("aria-label", "Toggle favorite");
    favBtn.innerHTML = `<img src="images/icons/${isFav(bg.id) ? "heart-filled" : "heart"}.svg" alt="">`;
    favBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleFav(bg.id);
      const nowFav = isFav(bg.id);
      card.classList.toggle("is-favorited", nowFav);
      favBtn.innerHTML = `<img src="images/icons/${nowFav ? "heart-filled" : "heart"}.svg" alt="">`;
      favBtn.classList.remove("is-fav");
      void favBtn.offsetWidth;
      favBtn.classList.add("is-fav");
      if (state.activeCategory === "favorites" && !nowFav) {
        applyFilters();
      }
    });

    const favBadge = document.createElement("div");
    favBadge.className = "fav-badge";
    favBadge.innerHTML = `<img src="images/icons/heart-filled.svg" alt="">1`;

    card.appendChild(img);
    card.appendChild(overlay);
    card.appendChild(favBtn);
    card.appendChild(favBadge);

    card.addEventListener("click", () => openPreview(bg.id));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openPreview(bg.id);
      }
    });

    observer.observe(card);
    return card;
  }

  function onIntersect(entries) {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const card = entry.target;
      const img = card.querySelector("img[data-src]");
      if (img) {
        img.src = img.dataset.src;
        img.removeAttribute("data-src");
        img.addEventListener("load", () => card.classList.remove("loading"), { once: true });
        img.addEventListener("error", () => card.classList.remove("loading"), { once: true });
      }
      observer.unobserve(card);
    });
  }

  // ---- Random button ------------------------------------------------------
  el.randomBtn.addEventListener("click", () => {
    if (!state.all.length) return;
    const pick = state.all[Math.floor(Math.random() * state.all.length)];
    openPreview(pick.id, state.all);
  });

  // ---- Preview --------------------------------------------------------------
  let previewList = [];

  function openPreview(id, listOverride) {
    previewList = listOverride || (state.filtered.length ? state.filtered : state.all);
    let idx = previewList.findIndex((b) => b.id === id);
    if (idx === -1) {
      // id came from a list not currently in previewList (e.g. random while filtered)
      previewList = state.all;
      idx = previewList.findIndex((b) => b.id === id);
    }
    state.previewIndex = idx;
    renderPreview();
    el.previewView.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closePreview() {
    el.previewView.hidden = true;
    document.body.style.overflow = "";
  }

  function renderPreview() {
    const bg = previewList[state.previewIndex];
    if (!bg) return;
    el.previewTitle.textContent = bg.title;
    el.previewCategory.textContent = bg.categoryName;
    el.previewImg.style.animation = "none";
    void el.previewImg.offsetWidth;
    el.previewImg.style.animation = "";
    el.previewImg.src = bg.filename;
    el.previewImg.alt = bg.title + " — full screen preview";
    resetZoom();
    updatePreviewFav();
    el.setToast.classList.remove("show");
    el.confettiWrap.innerHTML = "";
  }

  function updatePreviewFav() {
    const bg = previewList[state.previewIndex];
    const fav = isFav(bg.id);
    el.previewFav.classList.toggle("is-fav", fav);
    el.previewFavIcon.src = `images/icons/${fav ? "heart-filled" : "heart"}.svg`;
  }

  el.previewFav.addEventListener("click", () => {
    const bg = previewList[state.previewIndex];
    toggleFav(bg.id);
    updatePreviewFav();
    el.previewFav.classList.remove("is-fav");
    void el.previewFav.offsetWidth;
    updatePreviewFav();
    // reflect on grid card too
    const card = el.grid.querySelector(`.card[data-id="${cssEscape(bg.id)}"]`);
    if (card) {
      const nowFav = isFav(bg.id);
      card.classList.toggle("is-favorited", nowFav);
      const cardFavBtn = card.querySelector(".fav-btn img");
      if (cardFavBtn) cardFavBtn.src = `images/icons/${nowFav ? "heart-filled" : "heart"}.svg`;
    }
  });

  el.previewBack.addEventListener("click", closePreview);

  function goDelta(delta) {
    if (!previewList.length) return;
    state.previewIndex = (state.previewIndex + delta + previewList.length) % previewList.length;
    renderPreview();
  }
  el.prevBtn.addEventListener("click", () => goDelta(-1));
  el.nextBtn.addEventListener("click", () => goDelta(1));

  document.addEventListener("keydown", (e) => {
    if (el.previewView.hidden) return;
    if (e.key === "ArrowLeft") goDelta(-1);
    else if (e.key === "ArrowRight") goDelta(1);
    else if (e.key === "Escape") closePreview();
  });

  // ---- Swipe navigation -----------------------------------------------------
  (function setupSwipe() {
    let startX = 0, startY = 0, tracking = false;
    el.previewFrame.addEventListener("touchstart", (e) => {
      if (e.touches.length !== 1) { tracking = false; return; }
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      tracking = true;
    }, { passive: true });
    el.previewFrame.addEventListener("touchend", (e) => {
      if (!tracking) return;
      tracking = false;
      const dx = (e.changedTouches[0].clientX - startX);
      const dy = (e.changedTouches[0].clientY - startY);
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        goDelta(dx < 0 ? 1 : -1);
      }
    }, { passive: true });
  })();

  // ---- Pinch to zoom (basic) -------------------------------------------------
  (function setupPinchZoom() {
    let scale = 1, startDist = 0, startScale = 1;
    function dist(touches) {
      const [a, b] = touches;
      return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    }
    el.previewFrame.addEventListener("touchstart", (e) => {
      if (e.touches.length === 2) {
        startDist = dist(e.touches);
        startScale = scale;
      }
    }, { passive: true });
    el.previewFrame.addEventListener("touchmove", (e) => {
      if (e.touches.length === 2) {
        e.preventDefault();
        const newDist = dist(e.touches);
        scale = Math.min(3, Math.max(1, startScale * (newDist / startDist)));
        el.previewImg.style.transform = `scale(${scale})`;
      }
    }, { passive: false });
    window.resetZoom = function () {
      scale = 1;
      el.previewImg.style.transform = "";
    };
  })();
  function resetZoom() {
    if (window.resetZoom) window.resetZoom();
  }

  // ---- Set as Background (visual feedback only) ------------------------------
  el.setBgBtn.addEventListener("click", () => {
    launchConfetti();
    el.setToast.classList.add("show");
    playChime();
    clearTimeout(el.setToast._t);
    el.setToast._t = setTimeout(() => el.setToast.classList.remove("show"), 1800);
  });

  // ---- Download ----------------------------------------------------------------
  el.downloadBtn.addEventListener("click", () => {
    const bg = previewList[state.previewIndex];
    if (!bg) return;
    const a = document.createElement("a");
    a.href = bg.filename;
    a.download = bg.title.replace(/\s+/g, "-").toLowerCase() + ".svg";
    document.body.appendChild(a);
    a.click();
    a.remove();
  });

  // ---- Sound toggle ------------------------------------------------------------
  function updateSoundBtn() {
    el.soundToggle.setAttribute("aria-pressed", String(state.soundOn));
    el.soundIcon.src = `images/icons/${state.soundOn ? "sound-on" : "sound-off"}.svg`;
  }
  updateSoundBtn();
  el.soundToggle.addEventListener("click", () => {
    state.soundOn = !state.soundOn;
    localStorage.setItem(SOUND_KEY, String(state.soundOn));
    updateSoundBtn();
    if (state.soundOn) playChime();
  });

  function playChime() {
    if (!state.soundOn) return;
    try {
      if (!state.audioCtx) state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const ctx = state.audioCtx;
      const now = ctx.currentTime;
      const notes = [523.25, 659.25, 783.99, 1046.5]; // C5 E5 G5 C6
      notes.forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        const t0 = now + i * 0.09;
        gain.gain.setValueAtTime(0, t0);
        gain.gain.linearRampToValueAtTime(0.18, t0 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.35);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t0);
        osc.stop(t0 + 0.4);
      });
    } catch (e) { /* audio not available; ignore */ }
  }

  // ---- Confetti -------------------------------------------------------------------
  function launchConfetti() {
    const canvas = document.createElement("canvas");
    const wrap = el.confettiWrap;
    wrap.innerHTML = "";
    wrap.appendChild(canvas);
    const rect = wrap.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    const ctx = canvas.getContext("2d");
    const colors = ["#ff6fa5", "#ffd166", "#06d6a0", "#4cc9f0", "#9b5de5", "#ff9f1c"];
    const pieces = Array.from({ length: 140 }, () => ({
      x: Math.random() * canvas.width,
      y: -20 - Math.random() * canvas.height * 0.3,
      w: 6 + Math.random() * 6,
      h: 8 + Math.random() * 10,
      color: colors[Math.floor(Math.random() * colors.length)],
      speedY: 3 + Math.random() * 4,
      speedX: -2 + Math.random() * 4,
      rot: Math.random() * 360,
      rotSpeed: -8 + Math.random() * 16,
    }));
    let frame = 0;
    const maxFrames = 130;
    function tick() {
      frame++;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pieces.forEach((p) => {
        p.x += p.speedX;
        p.y += p.speedY;
        p.rot += p.rotSpeed;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rot * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      });
      if (frame < maxFrames) {
        requestAnimationFrame(tick);
      } else {
        wrap.innerHTML = "";
      }
    }
    requestAnimationFrame(tick);
  }

  // ---- Utilities ----------------------------------------------------------------
  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function cssEscape(s) {
    return window.CSS && CSS.escape ? CSS.escape(s) : s.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
  }
})();
