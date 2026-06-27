const API = "http://localhost:8000";

let currentData = [];  // last fetched results (full list)
let currentType = "all"; // active type filter

/* Helpers*/
function orgInitials(name) {
  return name.split(/[\s\/\-]/)[0].substring(0, 2).toUpperCase();
}

function typeLabel(type) {
  const map = {
    scholarship:   "منحة دراسية",
    internship:    "تدريب",
    job:           "وظيفة",
    summer_school: "مدرسة صيفية",
  };
  return map[type] || type;
}

function scoreLabel(score) {
  return Math.round(score * 100) + "% تطابق";
}

/* card renderer */
function buildCard(r) {
  const initials  = orgInitials(r.organisation);
  const label     = typeLabel(r.type);
  const pct       = Math.round((r.score || 0.75) * 100);
  const showScore = r.score !== undefined && r.score < 1;

  return `
    <article class="opp-card" tabindex="0" aria-label="${r.title_ar || r.title}">
      <div class="card-stripe ${r.type}"></div>
      <div class="card-body">
        <div class="card-org-row">
          <div class="org-logo" aria-hidden="true">${initials}</div>
          <span class="org-name">${r.organisation}</span>
        </div>
        <h3 class="card-title">${r.title_ar || r.title}</h3>
        <div class="card-location"> ${r.location || "—"}</div>
        <div class="card-tags">
          <span class="type-pill type-${r.type}">${label}</span>
          ${(r.tags || []).slice(0, 2).map(
            t => `<span class="type-pill type-${r.type}" style="opacity:0.6">${t}</span>`
          ).join("")}
        </div>
      </div>
      ${showScore ? `
        <div class="score-track">
          <div class="score-fill" style="width:${pct}%"></div>
        </div>
      ` : ""}
      <div class="card-footer">
        <span class="deadline-txt">${r.deadline}</span>
        ${showScore
          ? `<span class="score-badge">${scoreLabel(r.score)}</span>`
          : ""}
        <a class="card-link"
           href="${r.link}"
           target="_blank"
           rel="noopener noreferrer">
          تفاصيل
        </a>
      </div>
    </article>
  `;
}

/* ── Skeleton loading state ── */
function showSkeleton() {
  const grid = document.getElementById("cards-grid");
  grid.innerHTML = Array(6).fill(`
    <div class="opp-card" style="pointer-events:none">
      <div class="card-stripe"></div>
      <div class="card-body" style="gap:10px">
        <div class="card-org-row">
          <div class="skeleton" style="width:34px;height:34px;border-radius:6px"></div>
          <div class="skeleton" style="flex:1;height:12px"></div>
        </div>
        <div class="skeleton" style="height:16px;width:85%"></div>
        <div class="skeleton" style="height:12px;width:55%"></div>
        <div class="skeleton" style="height:20px;width:40%;border-radius:99px"></div>
      </div>
      <div class="card-footer" style="border-top:1px solid #efefef">
        <div class="skeleton" style="height:12px;width:80px"></div>
        <div class="skeleton" style="height:28px;width:60px;border-radius:4px"></div>
      </div>
    </div>
  `).join("");
}

/* Render results with meta bar  */
function renderCards(data, meta = {}) {
  const grid  = document.getElementById("cards-grid");
  const count = document.getElementById("section-count");

  let metaText = `${data.length} نتيجة`;
  if (meta.expired_filtered > 0) {
    metaText += ` · تم إخفاء ${meta.expired_filtered} فرصة منتهية الصلاحية`;
  }
  count.textContent = metaText;

  if (!data.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <p>لا توجد نتائج — جرب كلمات مختلفة</p>
      </div>`;
    return;
  }

  grid.innerHTML = data.map(buildCard).join("");
}

/*  Filter by type */
function filterType(type, el) {
  currentType = type;
  document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
  el.classList.add("active");

  const titles = {
    all:           "الفرص المتاحة",
    scholarship:   "المنح الدراسية",
    internship:    "برامج التدريب",
    job:           "فرص العمل",
    summer_school: "المدارس الصيفية",
  };
  document.getElementById("section-title").textContent = titles[type];

  const filtered = type === "all"
    ? currentData
    : currentData.filter(r => r.type === type);
  renderCards(filtered);
}

async function doSearch() {
  const heroInput = document.getElementById("hero-search-input");
  const navInput  = document.getElementById("nav-search-input");
  const query     = (heroInput.value || navInput.value).trim();
  if (!query) return;

  heroInput.value = query;
  navInput.value  = query;

  document.getElementById("section-title").textContent = `نتائج البحث: "${query}"`;
  showSkeleton();

  currentType = "all";
  document.querySelectorAll(".filter-chip").forEach((c, i) =>
    c.classList.toggle("active", i === 0)
  );

  try {
    const res = await fetch(`${API}/search`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: 15 }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data  = await res.json();
    currentData = data.results || [];

    renderCards(currentData, {
      expired_filtered: data.expired_filtered || 0
    });

    if (typeof initChatWithResults === "function") {
      initChatWithResults(currentData);
    }

  } catch (err) {
    console.error("Search error:", err);
    document.getElementById("cards-grid").innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <p>خطأ في الاتصال بالخادم — تأكد من تشغيل <code>uvicorn main:app</code></p>
      </div>`;
  }
}

function liveFilter(value) {
  document.getElementById("hero-search-input").value = value;
  if (!value.trim()) {
    renderCards(currentData);
    return;
  }
  const v        = value.toLowerCase();
  const filtered = currentData.filter(r =>
    [r.title_ar, r.title, r.organisation, r.location, ...(r.tags || [])]
      .join(" ").toLowerCase().includes(v)
  );
  renderCards(filtered);
}

function fillSearch(query) {
  document.getElementById("hero-search-input").value = query;
  document.getElementById("nav-search-input").value  = query;
  doSearch();
}

/* Tab switcher */
function switchTab(tab, el) {
  document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
  document.getElementById("tab-search").style.display = tab === "search" ? "block" : "none";
  document.getElementById("tab-chat").style.display   = tab === "chat"   ? "block" : "none";
}