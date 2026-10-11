/*
 * BDBV2026 — dashboard des présentations provinciales : moteur partagé.
 * Lit window.PAYLOAD (embarqué par Scripts/build_dashboard.py) et rend la page
 * indiquée par <body data-view="...">. Aucune dépendance externe.
 */
(function () {
  "use strict";

  const P = window.PAYLOAD || { meta: { dates: [] } };
  const META = P.meta || { dates: [] };
  const DATES = META.dates || [];
  const VIEW = document.body.dataset.view;

  // ── Formatting ────────────────────────────────────────────
  const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  const isNum = (v) => typeof v === "number" && isFinite(v);
  const fmt = (v) => (isNum(v) ? Math.round(v).toLocaleString("fr-FR").replace(/ /g, " ") : "–");
  const fmtPct = (v) => (isNum(v) ? v.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " %" : "–");
  const frDate = (iso) => {
    if (!iso) return "–";
    const [y, m, d] = iso.split("-").map(Number);
    return `${d} ${MONTHS[m - 1]} ${y}`;
  };
  const shortDate = (iso) => {
    if (!iso) return "";
    const [, m, d] = iso.split("-").map(Number);
    return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
  };
  const normKey = (s) => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sum = (rows, key) => {
    let s = 0, n = 0;
    for (const r of rows) if (isNum(r[key])) { s += r[key]; n++; }
    return n ? s : null;
  };
  const pct = (a, b) => (isNum(a) && isNum(b) && b > 0 ? (100 * a) / b : null);

  const TABLE_LABELS = { cases: "cas", alerts: "alertes", contacts: "contacts", alert_sources: "sources", alert_sources_wide: "sources" };
  const SOURCE_LABELS = {
    fosa_recherche_passive: "FOSA / recherche passive",
    recherche_active: "Recherche active",
    communaute: "Communauté",
    point_entree: "Points d'entrée (PoE/PoC)",
    suivi_contacts: "Suivi des contacts",
    autres: "Autres",
  };
  const SOURCE_ORDER = Object.keys(SOURCE_LABELS);

  // ── State: selected date (shared across pages through ?date=) ──
  const params = new URLSearchParams(location.search);
  let DATE = DATES.includes(params.get("date")) ? params.get("date") : META.latest_date || DATES[DATES.length - 1];
  const prevDate = (d) => {
    const i = DATES.indexOf(d);
    return i > 0 ? DATES[i - 1] : null;
  };
  const atDate = (rows, d) => (rows || []).filter((r) => r.date === d);

  const withDate = (href) => {
    const base = href.split("?")[0];
    return DATE ? `${base}?date=${DATE}` : base;
  };
  function syncLinks() {
    document.querySelectorAll("a.tab, a[data-keep-date], a.prov-link").forEach((a) => a.setAttribute("href", withDate(a.getAttribute("href"))));
  }
  const provLink = (prov) => {
    const f = (META.province_pages || {})[prov];
    return f ? `<a class="prov-link" href="${withDate(f)}">${esc(prov)}</a>` : esc(prov);
  };

  function initProvinceMenu() {
    const sel = document.getElementById("province-nav");
    if (!sel) return;
    sel.addEventListener("change", () => { if (sel.value) location.href = withDate(sel.value); });
  }

  function initDateSelect() {
    const sel = document.getElementById("date-select");
    if (!sel) return;
    if (!DATES.length) {
      sel.innerHTML = "<option>Aucune donnée</option>";
      sel.disabled = true;
      return;
    }
    sel.innerHTML = DATES.slice().reverse().map((d) => `<option value="${d}"${d === DATE ? " selected" : ""}>${frDate(d)}</option>`).join("");
    sel.addEventListener("change", () => {
      DATE = sel.value;
      const u = new URL(location.href);
      u.searchParams.set("date", DATE);
      history.replaceState(null, "", u);
      syncLinks();
      render();
    });
    syncLinks();
  }

  // ── Tooltip ───────────────────────────────────────────────
  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  function showTip(html, evt) {
    tip.innerHTML = html;
    tip.style.display = "block";
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
    tip.style.left = `${Math.max(8, x)}px`;
    tip.style.top = `${Math.max(8, y)}px`;
  }
  const hideTip = () => { tip.style.display = "none"; };
  const tipRows = (title, rows) =>
    `<strong>${esc(title)}</strong>` + rows.map(([k, v]) => `<div class="row"><span>${esc(k)}</span><span>${v}</span></div>`).join("");

  // ── Pills (status = icon + label, never colour alone) ─────
  // The dot carries the status colour, the label carries the meaning; `icon` is kept for
  // forced-colors / print, where it replaces the dot (see .pill .ic in dashboard.css).
  const pill = (kind, icon, label) => `<span class="pill ${kind}"><span class="dot" aria-hidden="true"></span><span class="ic" aria-hidden="true">${esc(icon || "")}</span>${esc(label)}</span>`;

  // ── Sortable table ────────────────────────────────────────
  function renderTable(el, columns, rows, opts = {}) {
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = `<p class="empty">${esc(opts.empty || "Aucune donnée pour cette date.")}</p>`;
      return;
    }
    let sortKey = opts.sortKey || null;
    let desc = opts.desc !== false;
    const draw = () => {
      const sorted = rows.slice();
      if (sortKey) {
        const col = columns.find((c) => c.key === sortKey);
        const val = col && col.sortValue ? col.sortValue : (r) => r[sortKey];
        sorted.sort((a, b) => {
          const va = val(a), vb = val(b);
          if (va == null && vb == null) return 0;
          if (va == null) return 1;
          if (vb == null) return -1;
          const c = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb), "fr");
          return desc ? -c : c;
        });
      }
      const head = columns.map((c) => {
        const active = c.key === sortKey;
        const aria = active ? ` aria-sort="${desc ? "descending" : "ascending"}"` : "";
        const sortable = c.sortable === false ? "" : " sortable";
        return `<th scope="col" class="${c.num ? "num" : ""}${sortable}" data-key="${c.key}" tabindex="${c.sortable === false ? -1 : 0}"${aria}>${esc(c.label)}${active ? `<span class="arrow">${desc ? "▼" : "▲"}</span>` : ""}</th>`;
      }).join("");
      const cell = (c, r) => {
        const v = c.render ? c.render(r) : c.fmt ? c.fmt(r[c.key]) : esc(r[c.key] == null ? "–" : r[c.key]);
        return `<td class="${c.num ? "num" : ""}${c.cls ? " " + c.cls : ""}">${v}</td>`;
      };
      const body = sorted.map((r) => `<tr>${columns.map((c) => cell(c, r)).join("")}</tr>`).join("");
      const total = opts.total ? `<tr class="total">${columns.map((c) => cell(c, opts.total)).join("")}</tr>` : "";
      el.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}${total}</tbody></table>`;
      el.querySelectorAll("th.sortable").forEach((th) => {
        const act = () => {
          const k = th.dataset.key;
          if (k === sortKey) desc = !desc; else { sortKey = k; desc = true; }
          draw();
        };
        th.addEventListener("click", act);
        th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); } });
      });
    };
    draw();
  }

  // ── SVG helpers ───────────────────────────────────────────
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs = {}, text) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  };
  const niceStep = (v, integer) => {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const f = v / p;
    const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
    return integer ? Math.max(1, Math.round(step)) : step;
  };
  const niceMax = (v) => {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const f = v / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  };
  // bar with 4px rounded data-end, square at the baseline
  const barPath = (x, y, w, h, r = 4) => {
    if (w <= 0) return "";
    r = Math.min(r, w, h / 2);
    return `M${x},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 ${-r},${r}h${-(w - r)}z`;
  };
  const widthOf = (el) => Math.max(280, Math.floor(el.clientWidth || el.parentElement.clientWidth || 600));

  /** Horizontal bars. items: [{label, value, tip: [[k, v]], note}] */
  function hbarChart(el, items, opts = {}) {
    if (!el) return;
    el.innerHTML = "";
    if (!items.length) { el.innerHTML = `<p class="empty">${esc(opts.empty || "Aucune donnée.")}</p>`; return; }
    const W = widthOf(el), rowH = 26, barH = 14, labelW = Math.min(170, Math.round(W * 0.34)), valW = 64;
    const H = items.length * rowH + 8;
    const fmtV = opts.format || fmt;
    const max = opts.max || niceMax(Math.max(...items.map((d) => (isNum(d.value) ? d.value : 0))));
    const plotW = W - labelW - valW;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria || "" });
    items.forEach((d, i) => {
      const y = i * rowH + 4;
      const g = svgEl("g");
      g.appendChild(svgEl("text", { x: labelW - 8, y: y + rowH / 2 + 4, "text-anchor": "end" }, d.label));
      if (isNum(d.value)) {
        const w = Math.max(d.value > 0 ? 2 : 0, (d.value / max) * plotW);
        g.appendChild(svgEl("path", { d: barPath(labelW, y + (rowH - barH) / 2, w, barH), fill: `var(${opts.color || "--series-1"})` }));
        g.appendChild(svgEl("text", { x: labelW + w + 6, y: y + rowH / 2 + 4, class: "value-label" }, fmtV(d.value)));
      } else {
        g.appendChild(svgEl("text", { x: labelW, y: y + rowH / 2 + 4, "font-style": "italic" }, d.note || "non extrait"));
      }
      const hit = svgEl("rect", { x: 0, y, width: W, height: rowH, class: "hit" });
      hit.addEventListener("mousemove", (e) => showTip(tipRows(d.label, d.tip || [[opts.valueLabel || "Valeur", fmtV(d.value)]]), e));
      hit.addEventListener("mouseleave", hideTip);
      g.appendChild(hit);
      svg.appendChild(g);
    });
    el.appendChild(svg);
  }

  /** Bullet bars: total (muted) with the achieved part overlaid (series-1). */
  function bulletChart(el, items, opts = {}) {
    if (!el) return;
    el.innerHTML = "";
    if (!items.length) { el.innerHTML = `<p class="empty">${esc(opts.empty || "Aucune donnée.")}</p>`; return; }
    el.insertAdjacentHTML("beforeend",
      `<div class="legend"><span><span class="sw" style="background:var(--series-muted)"></span>${esc(opts.totalLabel)}</span>` +
      `<span><span class="sw" style="background:var(--series-1)"></span>${esc(opts.partLabel)}</span></div>`);
    const W = widthOf(el), rowH = 26, barH = 14, labelW = Math.min(170, Math.round(W * 0.34)), valW = 110;
    const H = items.length * rowH + 8;
    const max = niceMax(Math.max(...items.map((d) => d.total || 0)));
    const plotW = W - labelW - valW;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria || "" });
    items.forEach((d, i) => {
      const y = i * rowH + 4, by = y + (rowH - barH) / 2;
      svg.appendChild(svgEl("text", { x: labelW - 8, y: y + rowH / 2 + 4, "text-anchor": "end" }, d.label));
      const wt = isNum(d.total) ? Math.max(d.total > 0 ? 2 : 0, (d.total / max) * plotW) : 0;
      const wp = isNum(d.part) ? Math.max(d.part > 0 ? 2 : 0, (d.part / max) * plotW) : 0;
      if (wt) svg.appendChild(svgEl("path", { d: barPath(labelW, by, wt, barH), fill: "var(--series-muted)" }));
      if (wp) svg.appendChild(svgEl("path", { d: barPath(labelW, by + 3, wp, barH - 6, 3), fill: "var(--series-1)" }));
      svg.appendChild(svgEl("text", { x: labelW + Math.max(wt, wp) + 6, y: y + rowH / 2 + 4, class: "value-label" },
        `${fmt(d.part)} / ${fmt(d.total)}`));
      const hit = svgEl("rect", { x: 0, y, width: W, height: rowH, class: "hit" });
      hit.addEventListener("mousemove", (e) => showTip(tipRows(d.label, [[opts.totalLabel, fmt(d.total)], [opts.partLabel, fmt(d.part)], ["Taux", fmtPct(pct(d.part, d.total))]]), e));
      hit.addEventListener("mouseleave", hideTip);
      svg.appendChild(hit);
    });
    el.appendChild(svg);
  }

  /** 100 % stacked bars. rows: [{label, parts: {key: value}}], keys in fixed order. */
  function stackedChart(el, rows, keys, labels, opts = {}) {
    if (!el) return;
    el.innerHTML = "";
    if (!rows.length) { el.innerHTML = `<p class="empty">${esc(opts.empty || "Aucune donnée.")}</p>`; return; }
    const used = keys.filter((k) => rows.some((r) => (r.parts[k] || 0) > 0));
    const color = (k) => `var(--series-${keys.indexOf(k) + 1})`; // colour follows the entity, never its rank
    el.insertAdjacentHTML("beforeend", `<div class="legend">${used.map((k) => `<span><span class="sw" style="background:${color(k)}"></span>${esc(labels[k])}</span>`).join("")}</div>`);
    const W = widthOf(el), rowH = 30, barH = 18, labelW = Math.min(130, Math.round(W * 0.28)), valW = 54;
    const H = rows.length * rowH + 8, plotW = W - labelW - valW;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria || "" });
    rows.forEach((r, i) => {
      const y = i * rowH + 4, by = y + (rowH - barH) / 2;
      const total = used.reduce((s, k) => s + (r.parts[k] || 0), 0);
      svg.appendChild(svgEl("text", { x: labelW - 8, y: y + rowH / 2 + 4, "text-anchor": "end" }, r.label));
      let x = labelW;
      used.forEach((k) => {
        const v = r.parts[k] || 0;
        if (!v || !total) return;
        const w = (v / total) * plotW;
        const seg = svgEl("rect", { x: x, y: by, width: Math.max(0, w - 2), height: barH, rx: 2, fill: color(k) }); // 2px surface gap
        seg.addEventListener("mousemove", (e) => showTip(tipRows(`${r.label} — ${labels[k]}`, [["Alertes", fmt(v)], ["Part", fmtPct(pct(v, total))]]), e));
        seg.addEventListener("mouseleave", hideTip);
        svg.appendChild(seg);
        x += w;
      });
      svg.appendChild(svgEl("text", { x: labelW + plotW + 6, y: y + rowH / 2 + 4, class: "value-label" }, fmt(total)));
    });
    el.appendChild(svg);
  }

  /** Line chart over dates, single series, crosshair + tooltip. points: [{date, value}] */
  function lineChart(el, points, opts = {}) {
    if (!el) return;
    el.innerHTML = "";
    const pts = points.filter((p) => isNum(p.value));
    if (!pts.length) { el.innerHTML = `<p class="empty">${esc(opts.empty || "Pas de valeur extraite.")}</p>`; return; }
    const W = widthOf(el), H = opts.height || 180;
    const m = { l: 48, r: 16, t: 14, b: 26 };
    const pw = W - m.l - m.r, ph = H - m.t - m.b;
    const fmtV = opts.format || fmt;
    const t = (d) => Date.parse(d + "T00:00:00Z");
    const xs = DATES.map(t);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const X = (d) => (x1 === x0 ? m.l + pw / 2 : m.l + ((t(d) - x0) / (x1 - x0)) * pw);
    const step = opts.max ? opts.max / 4 : niceStep(Math.max(...pts.map((p) => p.value)) / 4, !opts.pct);
    const vmax = opts.max || Math.max(step, Math.ceil(Math.max(...pts.map((p) => p.value)) / step) * step);
    const Y = (v) => m.t + ph - (v / vmax) * ph;
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria || "" });
    for (let v = 0, i = 0; v <= vmax + 1e-9; v += step, i++) {
      const y = Y(v);
      svg.appendChild(svgEl("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, class: i ? "gridline" : "axis-line" }));
      svg.appendChild(svgEl("text", { x: m.l - 6, y: y + 4, "text-anchor": "end" }, opts.pct ? `${Math.round(v)} %` : fmt(v)));
    }
    const ticks = DATES.length <= 8 ? DATES : DATES.filter((_, i) => i % Math.ceil(DATES.length / 8) === 0);
    ticks.forEach((d) => svg.appendChild(svgEl("text", { x: X(d), y: H - 6, "text-anchor": "middle" }, shortDate(d))));
    if (pts.length > 1) {
      svg.appendChild(svgEl("path", {
        d: pts.map((p, i) => `${i ? "L" : "M"}${X(p.date).toFixed(1)},${Y(p.value).toFixed(1)}`).join(""),
        fill: "none", stroke: "var(--series-1)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
      }));
    }
    if (pts.length <= 40) {
      pts.forEach((p) => svg.appendChild(svgEl("circle", {
        cx: X(p.date), cy: Y(p.value), r: p.date === DATE ? 5.5 : 4,
        fill: "var(--series-1)", stroke: "var(--surface-chart)", "stroke-width": 2,
      })));
    }
    const last = pts[pts.length - 1];
    svg.appendChild(svgEl("text", { x: Math.min(X(last.date) + 8, W - m.r), y: Y(last.value) - 8, class: "value-label", "text-anchor": X(last.date) > W - 60 ? "end" : "start" }, fmtV(last.value)));
    const cross = svgEl("line", { y1: m.t, y2: m.t + ph, class: "crosshair", visibility: "hidden" });
    svg.appendChild(cross);
    const hit = svgEl("rect", { x: m.l, y: m.t, width: pw, height: ph, class: "hit" });
    hit.addEventListener("mousemove", (e) => {
      const r = svg.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * W;
      let best = pts[0];
      for (const p of pts) if (Math.abs(X(p.date) - px) < Math.abs(X(best.date) - px)) best = p;
      cross.setAttribute("x1", X(best.date)); cross.setAttribute("x2", X(best.date));
      cross.setAttribute("visibility", "visible");
      showTip(tipRows(frDate(best.date), [[opts.label || "Valeur", fmtV(best.value)]].concat(best.extra || [])), e);
    });
    hit.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
    svg.appendChild(hit);
    el.appendChild(svg);
  }

  // ── Province filter chips (zones / alerts pages) ──────────
  function initChips(el, provinces, onChange) {
    if (!el) return () => "";
    let current = "";
    const draw = () => {
      el.innerHTML = [["", "Toutes les provinces"]].concat(provinces.map((p) => [p, p]))
        .map(([v, l]) => `<button type="button" class="chip" data-v="${esc(v)}" aria-pressed="${v === current}">${esc(l)}</button>`).join("");
      el.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => { current = b.dataset.v; draw(); onChange(); }));
    };
    draw();
    return () => current;
  }

  // ── Extraction coverage helpers ───────────────────────────
  function coverage(date) {
    const qa = atDate(P.qa, date);
    return atDate(P.summary, date).map((s) => {
      const ok = (s.tables_extraites || "").split(";").filter(Boolean).map((k) => (k.startsWith("alert_sources") ? "alert_sources" : k));
      const missing = (s.tables_manquantes || "").split(";").filter(Boolean);
      const image = {};
      missing.forEach((k) => {
        const f = qa.find((q) => q.province === s.province && q.check === `table_absente_${k}`);
        image[k] = !!(f && /image/i.test(f.detail));
      });
      return { province: s.province, ok, missing, image };
    });
  }

  function missingSentence(date) {
    const parts = coverage(date).filter((c) => c.missing.length).map((c) => {
      const kinds = c.missing.map((k) => TABLE_LABELS[k] || k).join(", ");
      const img = c.missing.some((k) => c.image[k]) ? " — tableaux collés en image" : "";
      return `<strong>${esc(c.province)}</strong> (${esc(kinds)}${img})`;
    });
    return parts.length ? `Données incomplètes le ${frDate(date)} : ${parts.join(" ; ")}. Les totaux ne couvrent que les tableaux extraits.` : "";
  }


  // ── Map (SVG, geometry from window.GEO = assets/geo.js) ───
  // Geometry: BDBV2026-Data shapefile data/shapefiles/DRC_Health_zones.shp (see Scripts/common/geo.py).
  const MAP_BINS = {
    cumul_confirmes: { bins: [1, 10, 50, 200, 500], label: "Cumul des cas confirmés" },
    confirmes_21j: { bins: [1, 5, 20, 50, 100], label: "Confirmés sur 21 jours" },
  };
  const binLabels = (bins) => bins.map((b, i) => (i < bins.length - 1 ? `${fmt(b)}–${fmt(bins[i + 1] - 1)}` : `≥ ${fmt(b)}`));
  let mapMetric = "cumul_confirmes";
  let mapRedraw = null;

  function zoneStatusKey(r) {
    const j = r && r.jours_depuis_dernier_cas;
    if (!isNum(j)) return null;
    return j <= 21 ? "active" : j <= 42 ? "watch" : "clear";
  }
  const STATUS = {
    active: { fill: "var(--critical)", label: "Active (≤ 21 j)" },
    watch: { fill: "var(--warning)", label: "Surveillance (22–42 j)" },
    clear: { fill: "var(--good)", label: "Sans cas > 42 j" },
  };

  function initMapControls(redraw) {
    mapRedraw = redraw;
    document.querySelectorAll(".seg-btn[data-metric]").forEach((b) => {
      b.addEventListener("click", () => {
        mapMetric = b.dataset.metric;
        document.querySelectorAll(".seg-btn[data-metric]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        if (mapRedraw) mapRedraw();
      });
    });
  }

  /** opts: { focus: [province…] (fit + emphasis), linkProvinces: bool } */
  function mapChart(el, opts = {}) {
    if (!el) return;
    el.innerHTML = "";
    const G = window.GEO;
    if (!G || !G.zones || !G.zones.features.length) {
      el.innerHTML = '<p class="empty">Carte indisponible : shapefile des zones de santé absent au moment du build (BDBV2026-Data/data/shapefiles/DRC_Health_zones.shp).</p>';
      return;
    }
    const crop = !!opts.crop && (opts.focus || []).some((p) => G.bounds[p]);
    const focus = (crop ? opts.focus : Object.keys(G.bounds)).filter((p) => G.bounds[p]);
    const C = crop ? null : G.country;   // DRC silhouette on the general view only
    if (!focus.length) { el.innerHTML = '<p class="empty">Aucune zone de santé à afficher pour cette sélection.</p>'; return; }

    // data for the selected date
    const rows = Object.fromEntries(atDate(P.cases, DATE).map((r) => [r.zone, r]));
    const summary = Object.fromEntries(atDate(P.summary, DATE).map((r) => [r.province, r]));
    const cov = Object.fromEntries(coverage(DATE).map((c) => [c.province, c]));
    const casesOk = (prov) => cov[prov] && cov[prov].ok.includes("cases");
    const has21 = {};
    atDate(P.cases, DATE).forEach((r) => { if (isNum(r.confirmes_21j)) has21[r.province] = true; });
    const hasStatus = {};
    atDate(P.cases, DATE).forEach((r) => { if (isNum(r.jours_depuis_dernier_cas)) hasStatus[r.province] = true; });

    // projection: equirectangular, x scaled by cos(latitude) (DRC straddles the equator)
    let [x0, y0, x1, y1] = [180, 90, -180, -90];
    (C && C.bounds ? [C.bounds] : focus.map((p) => G.bounds[p])).forEach((b) => { x0 = Math.min(x0, b[0]); y0 = Math.min(y0, b[1]); x1 = Math.max(x1, b[2]); y1 = Math.max(y1, b[3]); });
    const kx = Math.cos(((y0 + y1) / 2) * Math.PI / 180);
    const padX = (x1 - x0) * 0.04 + 0.05, padY = (y1 - y0) * 0.04 + 0.05;
    x0 -= padX; x1 += padX; y0 -= padY; y1 += padY;
    const W = widthOf(el);
    const aspect = ((y1 - y0) / ((x1 - x0) * kx));
    const H = Math.round(Math.max(320, Math.min(620, W * aspect)));
    const scale = Math.min(W / ((x1 - x0) * kx), H / (y1 - y0));
    const ox = (W - (x1 - x0) * kx * scale) / 2, oy = (H - (y1 - y0) * scale) / 2;
    const X = (lon) => ox + (lon - x0) * kx * scale;
    const Y = (lat) => oy + (y1 - lat) * scale;
    const ringPath = (ring) => ring.map((c, i) => `${i ? "L" : "M"}${X(c[0]).toFixed(1)},${Y(c[1]).toFixed(1)}`).join("") + "Z";
    const geomPath = (g) => (g.type === "Polygon" ? [g.coordinates] : g.coordinates).map((poly) => poly.map(ringPath).join("")).join("");
    const linePath = (g) => g.coordinates.map((l) => l.map((c, i) => `${i ? "L" : "M"}${X(c[0]).toFixed(1)},${Y(c[1]).toFixed(1)}`).join("")).join("");

    const metric = mapMetric;
    const cfg = MAP_BINS[metric];
    const fillFor = (nom, prov) => {
      if (!summary[prov]) return { fill: "none", cls: "nodata" };                 // presentation not received
      if (!casesOk(prov)) return { fill: "url(#hatch)", cls: "hatch" };           // table not extracted
      const r = rows[nom];
      if (metric === "statut") {
        if (!hasStatus[prov]) return { fill: "url(#hatch)", cls: "hatch" };
        const k = zoneStatusKey(r);
        return k ? { fill: STATUS[k].fill } : { fill: "var(--neutral-bg)", cls: "none-reported" };
      }
      if (metric === "confirmes_21j" && !has21[prov]) return { fill: "url(#hatch)", cls: "hatch" };
      const v = r ? r[metric] : null;
      if (!isNum(v) || v <= 0) return { fill: "var(--neutral-bg)", cls: "none-reported" };
      let k = 0;
      cfg.bins.forEach((b, i) => { if (v >= b) k = i; });
      return { fill: `var(--seq-${k + 1})` };
    };

    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Carte des zones de santé — ${metric === "statut" ? "statut" : cfg.label}` });
    const defs = svgEl("defs");
    const pat = svgEl("pattern", { id: "hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
    pat.appendChild(svgEl("rect", { width: 6, height: 6, fill: "var(--neutral-bg)" }));
    pat.appendChild(svgEl("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "var(--muted)", "stroke-width": 1.4 }));
    defs.appendChild(pat);
    svg.appendChild(defs);
    const g = svgEl("g", { class: "map-layer" });
    svg.appendChild(g);

    const focusSet = new Set(focus);
    if (C) {
      (C.zones.features || []).forEach((f) => g.appendChild(svgEl("path", { d: geomPath(f.geometry), class: "country-zone", "vector-effect": "non-scaling-stroke" })));
      (C.outlines.features || []).forEach((f) => g.appendChild(svgEl("path", { d: linePath(f.geometry), class: "country-outline", fill: "none", "vector-effect": "non-scaling-stroke" })));
    }
    G.zones.features.forEach((f) => {
      const { nom, province: prov } = f.properties;
      if (!focusSet.has(prov)) return;   // province view: that province only
      const st = fillFor(nom, prov);
      const path = svgEl("path", { d: geomPath(f.geometry), fill: st.fill, class: `zone ${st.cls || ""}`, "vector-effect": "non-scaling-stroke" });
      path.addEventListener("mousemove", (e) => {
        const r = rows[nom];
        let lines;
        if (!summary[prov]) lines = [["", "Présentation non reçue"]];
        else if (!casesOk(prov)) lines = [["", "Tableau des cas non extrait"]];
        else if (!r) lines = [["", "Aucun cas rapporté"]];
        else lines = [["Confirmés (cumul)", fmt(r.cumul_confirmes)], ["Décès (cumul)", fmt(r.cumul_deces)],
          ["Confirmés 21 j", fmt(r.confirmes_21j)], ["Dernier cas", frDate(r.date_dernier_cas)],
          ["Statut", zoneStatusKey(r) ? STATUS[zoneStatusKey(r)].label : "–"]];
        showTip(tipRows(`${nom} — ${prov}`, lines), e);
      });
      path.addEventListener("mouseleave", hideTip);
      if (opts.linkProvinces && prov !== document.body.dataset.province && (META.province_pages || {})[prov]) {
        path.style.cursor = "pointer";
        path.addEventListener("click", () => { location.href = withDate(META.province_pages[prov]); });
      }
      g.appendChild(path);
    });
    (G.provinces.features || []).forEach((f) => {
      if (!focusSet.has(f.properties.province)) return;
      g.appendChild(svgEl("path", { d: linePath(f.geometry), class: `prov-outline${crop ? " focus" : ""}`, fill: "none", "vector-effect": "non-scaling-stroke" }));
    });
    focus.forEach((p) => {
      const c = (G.labels || {})[p];
      if (!c) return;
      g.appendChild(svgEl("text", { x: X(c[0]), y: Y(c[1]), class: "prov-label", "text-anchor": "middle" }, p));
    });
    el.appendChild(svg);

    // zoom / pan (buttons, double-click, drag)
    let s = 1, tx = 0, ty = 0;
    const apply = () => {
      g.setAttribute("transform", `translate(${tx},${ty}) scale(${s})`);
      g.querySelectorAll(".prov-label").forEach((t) => t.setAttribute("font-size", 12 / s));
    };
    const zoomAt = (f, cx = W / 2, cy = H / 2) => {
      const ns = Math.max(1, Math.min(12, s * f));
      tx = cx - ((cx - tx) * ns) / s; ty = cy - ((cy - ty) * ns) / s; s = ns;
      if (s === 1) { tx = 0; ty = 0; }
      apply();
    };
    const toSvg = (e) => { const r = svg.getBoundingClientRect(); return [((e.clientX - r.left) / r.width) * W, ((e.clientY - r.top) / r.height) * H]; };
    svg.addEventListener("dblclick", (e) => { e.preventDefault(); const [cx, cy] = toSvg(e); zoomAt(2, cx, cy); });
    let drag = null;
    svg.addEventListener("pointerdown", (e) => { if (s > 1) { drag = { x: e.clientX, y: e.clientY, tx, ty }; svg.setPointerCapture(e.pointerId); } });
    svg.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const r = svg.getBoundingClientRect();
      tx = drag.tx + ((e.clientX - drag.x) / r.width) * W; ty = drag.ty + ((e.clientY - drag.y) / r.height) * H; apply();
    });
    svg.addEventListener("pointerup", () => { drag = null; });
    const ctr = document.createElement("div");
    ctr.className = "map-controls";
    ctr.innerHTML = '<button type="button" aria-label="Zoomer">+</button><button type="button" aria-label="Dézoomer">−</button><button type="button" aria-label="Réinitialiser la vue">⟲</button>';
    const [bIn, bOut, bReset] = ctr.querySelectorAll("button");
    bIn.addEventListener("click", () => zoomAt(1.6));
    bOut.addEventListener("click", () => zoomAt(1 / 1.6));
    bReset.addEventListener("click", () => { s = 1; tx = 0; ty = 0; apply(); });
    el.appendChild(ctr);
    apply();

    // legend (identity never by colour alone: every swatch is labelled)
    const items = metric === "statut"
      ? Object.values(STATUS).map((st) => [st.fill, st.label])
      : binLabels(cfg.bins).map((l, i) => [`var(--seq-${i + 1})`, l]);
    const used = new Set([...g.querySelectorAll(".zone")].map((z) => z.getAttribute("class")));
    const extra = [["var(--neutral-bg)", "Aucun cas rapporté"]];
    if ([...used].some((c) => c.includes("hatch"))) extra.push(["hatch", metric === "cumul_confirmes" ? "Tableau non extrait (image)" : "Non extrait / non rapporté"]);
    if ([...used].some((c) => c.includes("nodata"))) extra.push(["none", "Présentation non reçue"]);
    const leg = document.createElement("div");
    leg.className = "legend map-legend";
    leg.innerHTML = `<span class="legend-title">${esc(metric === "statut" ? "Statut (jours depuis le dernier cas)" : cfg.label)}</span>` +
      items.concat(extra).map(([c, l]) => `<span><span class="sw${c === "hatch" ? " sw-hatch" : c === "none" ? " sw-none" : ""}" style="${c.startsWith("var") ? `background:${c}` : ""}"></span>${esc(l)}</span>`).join("");
    el.appendChild(leg);
  }


  // ════════════════════════════════════════════════════════════
  // Leaflet map — same design as BDBV2026-Epidemic_Dashboard/index.html
  // (no basemap: the DRC silhouette with the concerned provinces coloured on
  // the general view, the province alone on a province view; brand OUTBREAK ramp on a log scale, #111 hairline zone
  // borders scaled with zoom, amber #ffae42 hover, dark focus border, province
  // outlines #9b7d4e in their own pane, floating Couche / Légende / Zone panels).
  // Falls back to the SVG map above when Leaflet could not load (offline).
  // ════════════════════════════════════════════════════════════
  const OUTBREAK = [[246, 227, 223], [232, 179, 166], [208, 129, 99], [170, 74, 50], [124, 29, 29]];
  const PURPLES = [[211, 196, 224], [184, 164, 201], [150, 124, 171], [117, 90, 140], [91, 68, 112], [72, 52, 90], [55, 40, 72], [42, 30, 56]];
  const VIRIDIS = [[68, 1, 84], [72, 40, 120], [62, 73, 137], [49, 104, 142], [38, 130, 142], [31, 158, 137], [53, 183, 121], [109, 206, 89], [180, 222, 44], [253, 231, 37]];
  const ZERO_FILL = "#c4bfb6";
  const HOVER_COLOR = "#ffae42";
  const STATUS_HEX = { active: "#d03b3b", watch: "#fab219", clear: "#0ca30c" };
  const lerpColor = (stops, t) => {
    if (t <= 0) return stops[0];
    if (t >= 1) return stops[stops.length - 1];
    const x = t * (stops.length - 1), i = Math.floor(x), f = x - i, a = stops[i], b = stops[i + 1];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  };
  const rgbStr = (c) => `rgb(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])})`;
  const sumOrNull = (...vals) => (vals.some(isNum) ? vals.reduce((a, v) => a + (isNum(v) ? v : 0), 0) : null);

  const MAP_LAYERS = [
    { id: "cumul_confirmes", label: "Cas confirmés (cumul)", kind: "cases", scale: "log", palette: OUTBREAK, get: (r) => r.cumul_confirmes, zero: "0 / aucun cas rapporté" },
    { id: "cumul_deces", label: "Décès confirmés (cumul)", kind: "cases", scale: "log", palette: OUTBREAK, get: (r) => r.cumul_deces, zero: "0 / aucun décès rapporté" },
    { id: "confirmes_21j", label: "Cas confirmés — 21 derniers jours", kind: "cases", scale: "log", palette: OUTBREAK, get: (r) => r.confirmes_21j, needs: "confirmes_21j", zero: "0 cas sur 21 jours" },
    { id: "statut", label: "Statut des zones de santé", kind: "cases", categorical: true, needs: "jours_depuis_dernier_cas" },
    { id: "nouvelles_alertes", label: "Nouvelles alertes", kind: "alerts", scale: "log", palette: PURPLES, get: (r) => sumOrNull(r.nouvelles_alertes_vivants, r.nouvelles_alertes_deces), zero: "0 / aucune alerte rapportée" },
    { id: "contacts_a_suivre", label: "Contacts à suivre", kind: "contacts", scale: "log", palette: PURPLES, get: (r) => r.a_suivre, zero: "0 / aucun contact" },
    { id: "taux_suivi", label: "Taux de suivi des contacts (%)", kind: "contacts", scale: "linear", palette: VIRIDIS, domain: [0, 100], get: (r) => (isNum(r.a_suivre) && r.a_suivre > 0 && isNum(r.vus) ? (100 * r.vus) / r.a_suivre : null), round: 1 },
  ];
  const STATUS_LABELS = { active: "Active (dernier cas ≤ 21 j)", watch: "Surveillance (22–42 j)", clear: "Sans cas depuis > 42 j" };

  let LMAP = null; // the page's map instance (one per page)

  function mapData() {
    const byZone = (rows) => Object.fromEntries(rows.filter((r) => r.zone).map((r) => [r.zone, r]));
    const alertsZone = atDate(P.alerts_zone, DATE);
    const zoneAlertProvs = new Set(alertsZone.map((r) => r.province));
    // provinces that only give alerts per aire de santé: aggregate to the zone
    const aireAgg = {};
    atDate(P.alerts_aire, DATE).filter((r) => r.zone && !zoneAlertProvs.has(r.province)).forEach((r) => {
      const a = aireAgg[r.zone] || (aireAgg[r.zone] = { zone: r.zone, province: r.province });
      ["nouvelles_alertes_vivants", "nouvelles_alertes_deces", "total_alertes", "validees_vivants", "validees_deces"].forEach((k) => {
        if (isNum(r[k])) a[k] = (a[k] || 0) + r[k];
      });
    });
    const cov = Object.fromEntries(coverage(DATE).map((c) => [c.province, c]));
    const has = {};
    atDate(P.cases, DATE).forEach((r) => {
      ["confirmes_21j", "jours_depuis_dernier_cas"].forEach((k) => { if (isNum(r[k])) (has[k] || (has[k] = new Set())).add(r.province); });
    });
    return {
      tables: { cases: byZone(atDate(P.cases, DATE)), alerts: { ...aireAgg, ...byZone(alertsZone) }, contacts: byZone(atDate(P.contacts, DATE)) },
      summary: Object.fromEntries(atDate(P.summary, DATE).map((r) => [r.province, r])),
      cov, has,
    };
  }

  /** {state: none|notextracted|notreported|zero|value|cat, v, key} */
  function zoneValue(layer, nom, prov, D) {
    if (!D.summary[prov]) return { state: "none", why: "Présentation non reçue" };
    const c = D.cov[prov];
    if (!c || !c.ok.includes(layer.kind)) {
      return { state: "notextracted", why: c && c.image[layer.kind] ? "Tableau collé en image (non extrait)" : "Tableau non extrait" };
    }
    if (layer.needs && !(D.has[layer.needs] && D.has[layer.needs].has(prov))) {
      return { state: "notreported", why: "Non rapporté par la province" };
    }
    const row = D.tables[layer.kind][nom];
    if (layer.categorical) {
      const k = zoneStatusKey(row);
      return k ? { state: "cat", key: k } : { state: "zero", why: "Aucun cas rapporté" };
    }
    if (!row) return layer.domain ? { state: "notreported", why: "Aucun contact listé" } : { state: "zero", v: 0 };
    const v = layer.get(row);
    if (!isNum(v)) return { state: "notreported", why: "Non rapporté" };
    return v > 0 || layer.domain ? { state: "value", v } : { state: "zero", v: 0 };
  }

  function mapView(root, opts = {}) {
    if (!root) return;
    const G = window.GEO;
    if (!G || !G.zones || !G.zones.features.length) {
      root.innerHTML = '<p class="empty map-empty">Carte indisponible : shapefile des zones de santé absent au moment du build (BDBV2026-Data/data/shapefiles/DRC_Health_zones.shp).</p>';
      return;
    }
    if (!window.L) {
      // offline: Leaflet (unpkg) unreachable -> simplified SVG map
      if (!root.dataset.fallback) {
        root.dataset.fallback = "1";
        root.innerHTML = '<p class="map-fallback-note">Carte simplifiée (bibliothèque Leaflet indisponible hors ligne).</p><div class="map"></div>';
      }
      mapChart(root.querySelector(".map"), { focus: opts.focus, crop: opts.crop, linkProvinces: true });
      return;
    }
    if (!LMAP || LMAP.root !== root) LMAP = createLeafletMap(root);
    LMAP.update(opts);
  }

  function createLeafletMap(root) {
    const G = window.GEO;
    const full = root.dataset.mapMode === "full";
    root.innerHTML = `
      <div class="lmap"></div>
      <div class="mpanel m-controls">
        <div class="panel-header"><strong>Couche</strong><button class="panel-toggle" type="button" aria-label="Replier / déplier le panneau Couche" title="Replier / déplier">−</button></div>
        <div class="panel-body">
          <div class="zs-wrap">
            <input type="search" class="zs-input" autocomplete="off" spellcheck="false" placeholder="Rechercher une zone de santé…" aria-label="Rechercher une zone de santé" aria-autocomplete="list" aria-expanded="false">
            <div class="zs-results" role="listbox" hidden></div>
          </div>
          <label class="m-label">Source</label>
          <select class="m-layer" aria-label="Couche affichée">${MAP_LAYERS.map((l) => `<option value="${l.id}">${esc(l.label)}</option>`).join("")}</select>
          <div class="m-meta"></div>
        </div>
      </div>
      <div class="mpanel m-legend">
        <div class="panel-header"><div class="m-legend-title"><strong>Légende</strong></div><button class="panel-toggle" type="button" aria-label="Replier / déplier la légende" title="Replier / déplier">−</button></div>
        <div class="panel-body">
          <div class="legend-bar"></div><div class="legend-ticks"></div><div class="legend-scale"></div>
          <div class="legend-cats"></div><div class="legend-gray"></div>
        </div>
      </div>
      <div class="mpanel m-info">
        <div class="panel-header"><strong>Zone</strong><button class="panel-toggle" type="button" aria-label="Replier / déplier le détail de la zone" title="Replier / déplier">−</button></div>
        <div class="panel-body m-info-body info-empty">Cliquez sur une zone de santé.</div>
      </div>`;
    root.querySelectorAll(".panel-toggle").forEach((b) => b.addEventListener("click", () => {
      const panel = b.closest(".mpanel");
      const c = panel.classList.toggle("collapsed");
      b.textContent = c ? "+" : "−";
    }));
    if (window.matchMedia && window.matchMedia("(max-width: 700px)").matches) {
      root.querySelectorAll(".mpanel").forEach((pnl) => { pnl.classList.add("collapsed"); pnl.querySelector(".panel-toggle").textContent = "+"; });
    }

    // No basemap (no tile API, no neighbouring country). Two scopes:
    //  - "country" (general view): the DRC silhouette -- the other provinces
    //    in light grey (window.GEO.country) -- and the concerned provinces'
    //    zones coloured on top;
    //  - "province" (a province page, or a province chosen on Zones de santé):
    //    only that province's zones and outline, cropped to its extent.
    const map = L.map(root.querySelector(".lmap"), {
      zoomControl: !full, scrollWheelZoom: full, zoomSnap: 0.25,
      attributionControl: true, maxBoundsViscosity: 1.0,
    });
    map.attributionControl.setPrefix(false);
    map.attributionControl.addAttribution("Zones de santé : GRID3 COD v8.0 (BDBV2026-Data)");
    if (!full) map.zoomControl.setPosition("bottomright");
    const zoomWeight = (base) => base * Math.max(0.5, Math.min(2.1, 0.5 + (map.getZoom() - 5) * 0.28));

    const layerSelect = root.querySelector(".m-layer");
    const infoBody = root.querySelector(".m-info-body");
    let D = mapData();
    let selected = null;
    let domain = { min: 1, max: 10, isLog: true };
    let focusProvs = [];

    const layerDef = () => MAP_LAYERS.find((l) => l.id === layerSelect.value) || MAP_LAYERS[0];
    const colorFor = (v, layer) => {
      let t;
      if (domain.isLog) t = (Math.log(v) - Math.log(domain.min)) / (Math.log(domain.max) - Math.log(domain.min) || 1);
      else t = (v - domain.min) / (domain.max - domain.min || 1);
      return rgbStr(lerpColor(layer.palette, Math.max(0, Math.min(1, isFinite(t) ? t : 0))));
    };

    function styleFn(feature) {
      const { nom, province: prov } = feature.properties;
      const layer = layerDef();
      const z = zoneValue(layer, nom, prov, D);
      let st;
      if (z.state === "none") st = { color: "#111", weight: zoomWeight(0.35), fillOpacity: 0, dashArray: null };
      else if (z.state === "notextracted" || z.state === "notreported") st = { color: "#555", weight: zoomWeight(0.6), dashArray: "3 3", fillColor: ZERO_FILL, fillOpacity: 0.12 };
      else if (z.state === "zero") st = { color: "#111", weight: zoomWeight(0.35), dashArray: null, fillColor: ZERO_FILL, fillOpacity: 0.48 };
      else if (z.state === "cat") st = { color: "#111", weight: zoomWeight(0.35), dashArray: null, fillColor: STATUS_HEX[z.key], fillOpacity: 0.72 };
      else st = { color: "#111", weight: zoomWeight(0.35), dashArray: null, fillColor: colorFor(z.v, layer), fillOpacity: layer.palette === OUTBREAK ? 0.72 : 0.85 };
      if (nom === selected) Object.assign(st, { color: "#1a1a1a", weight: 2.4, dashArray: null });
      return st;
    }

    const fmtVal = (v, layer) => (layer.round ? fmtPct(v) : fmt(v));
    function tooltipHTML(feature) {
      const { nom, province: prov } = feature.properties;
      const layer = layerDef();
      const z = zoneValue(layer, nom, prov, D);
      const body = z.state === "value" ? `${esc(layer.label)} : ${fmtVal(z.v, layer)}`
        : z.state === "zero" ? esc(z.why || layer.zero || "0")
        : z.state === "cat" ? esc(STATUS_LABELS[z.key]) : esc(z.why);
      return `<strong>${esc(nom)}</strong> <span class="tt-prov">${esc(prov)}</span><br/>${body}`;
    }

    function infoHTML(nom, prov) {
      const c = D.tables.cases[nom], a = D.tables.alerts[nom], k = D.tables.contacts[nom];
      const s = D.summary[prov];
      const cov = D.cov[prov];
      const row = (l, v) => `<tr><td>${esc(l)}</td><td>${v}</td></tr>`;
      const section = (title, kind, rows) => {
        let h = `<h4>${esc(title)}</h4>`;
        if (!s) return h + '<p class="info-na">Présentation non reçue.</p>';
        if (!cov || !cov.ok.includes(kind)) return h + `<p class="info-na">${cov && cov.image[kind] ? "Tableau collé en image : non extrait." : "Tableau non extrait."}</p>`;
        return h + (rows ? `<table>${rows}</table>` : '<p class="info-na">Rien de rapporté pour cette zone.</p>');
      };
      let h = `<div class="info-title"><strong>${esc(nom)}</strong></div><div class="info-sub">${esc(prov)} · ${esc(frDate(DATE))}</div>`;
      h += section("Cas confirmés", "cases", c ? [
        row("Confirmés (cumul)", fmt(c.cumul_confirmes)), row("Décès (cumul)", fmt(c.cumul_deces)),
        row("Létalité", fmtPct(c.letalite)), row("Confirmés · 21 j", fmt(c.confirmes_21j)), row("Décès · 21 j", fmt(c.deces_21j)),
        row("Dernier cas", c.date_dernier_cas ? esc(frDate(c.date_dernier_cas)) : "–"), row("Jours depuis", fmt(c.jours_depuis_dernier_cas)),
        row("Statut", zoneStatusKey(c) ? esc(STATUS_LABELS[zoneStatusKey(c)]) : "–"),
      ].join("") : null);
      h += section("Alertes", "alerts", a ? [
        row("Nouvelles alertes", fmt(sumOrNull(a.nouvelles_alertes_vivants, a.nouvelles_alertes_deces))),
        row("dont décès", fmt(a.nouvelles_alertes_deces)), row("Total des alertes", fmt(a.total_alertes)),
        row("Validées (cas suspects)", fmt(sumOrNull(a.validees_vivants, a.validees_deces))),
      ].join("") : null);
      h += section("Suivi des contacts", "contacts", k ? [
        row("À suivre", fmt(k.a_suivre)), row("Vus", fmt(k.vus)), row("Taux de suivi", fmtPct(pct(k.vus, k.a_suivre) ?? k.taux_suivi_pct)),
        row("Nouveaux", fmt(k.nouveaux)), row("Devenus suspects", fmt(k.devenus_suspects)), row("Perdus de vue", fmt(k.perdus_de_vue)),
      ].join("") : null);
      const page = (META.province_pages || {})[prov];
      if (page && document.body.dataset.province !== prov) h += `<p class="info-link"><a class="prov-link" href="${withDate(page)}">Résumé de la province ${esc(prov)} →</a></p>`;
      return h;
    }

    function setSelection(nom, prov) {
      selected = selected === nom ? null : nom;
      geoLayer.setStyle(styleFn);
      if (selected) {
        geoLayer.eachLayer((l) => { if (l.feature.properties.nom === selected) l.bringToFront(); });
        infoBody.classList.remove("info-empty");
        infoBody.innerHTML = infoHTML(nom, prov);
        root.querySelector(".m-info").classList.remove("collapsed");
        root.querySelector(".m-info .panel-toggle").textContent = "−";
      } else {
        infoBody.classList.add("info-empty");
        infoBody.textContent = "Cliquez sur une zone de santé.";
      }
    }

    // DRC backdrop, below the zones (own pane, never interactive)
    const C = G.country || null;
    map.createPane("country");
    map.getPane("country").style.zIndex = 350;
    map.getPane("country").style.pointerEvents = "none";
    const css = getComputedStyle(document.documentElement);
    const BACKDROP = css.getPropertyValue("--map-backdrop").trim() || "#ebe8e2";
    const BACKDROP_LINE = css.getPropertyValue("--map-backdrop-line").trim() || "#c2baac";
    const countryLayers = C ? [
      L.geoJSON(C.zones, { pane: "country", interactive: false, style: () => ({ color: BACKDROP, weight: 0.8, opacity: 1, fillColor: BACKDROP, fillOpacity: 1 }) }),
      L.geoJSON(C.outlines, { pane: "country", interactive: false, style: () => ({ color: BACKDROP_LINE, weight: 0.9, opacity: 1, fillOpacity: 0 }) }),
    ] : [];
    let scope = null;
    let visibleZones = G.zones.features;
    let visibleOutlines = G.provinces.features;

    const geoLayer = L.geoJSON({ type: "FeatureCollection", features: [] }, {
      style: styleFn,
      onEachFeature: (feature, layer) => {
        layer.on({
          mouseover: (e) => {
            e.target.setStyle({ weight: 1.6, color: HOVER_COLOR, dashArray: null });
            e.target.bringToFront();
            e.target.bindTooltip(tooltipHTML(feature), { sticky: true, direction: "top", className: "zone-tooltip" }).openTooltip(e.latlng);
          },
          mouseout: (e) => {
            if (e.target.getTooltip()) e.target.unbindTooltip();
            geoLayer.resetStyle(e.target);
          },
          click: (e) => {
            L.DomEvent.stop(e);
            setSelection(feature.properties.nom, feature.properties.province);
          },
        });
      },
    }).addTo(map);

    map.createPane("province-outline");
    map.getPane("province-outline").style.zIndex = 550;
    map.getPane("province-outline").style.pointerEvents = "none";
    let highlightProvs = [];
    const outlineStyle = (f) => {
      const on = highlightProvs.includes(f.properties.province);
      // on the DRC view the concerned provinces stand out from the grey silhouette
      return { color: on ? "#b23b2e" : "#8a6a3a", weight: on ? 1.6 : 1.5, opacity: on ? 1 : 0.95, fillOpacity: 0 };
    };
    const outlineLayer = L.geoJSON({ type: "FeatureCollection", features: [] }, { pane: "province-outline", interactive: false, style: outlineStyle }).addTo(map);

    function setScope(nextScope, provs) {
      const key = nextScope + ":" + provs.join("|");
      if (key === scope) return false;
      scope = key;
      const only = new Set(provs);
      const crop = nextScope === "province";
      visibleZones = crop ? G.zones.features.filter((f) => only.has(f.properties.province)) : G.zones.features;
      visibleOutlines = crop ? G.provinces.features.filter((f) => only.has(f.properties.province)) : G.provinces.features;
      geoLayer.clearLayers();
      geoLayer.addData({ type: "FeatureCollection", features: visibleZones });
      outlineLayer.clearLayers();
      outlineLayer.addData({ type: "FeatureCollection", features: visibleOutlines });
      countryLayers.forEach((l) => { if (crop) l.remove(); else if (!map.hasLayer(l)) l.addTo(map); });
      if (selected && !visibleZones.some((f) => f.properties.nom === selected)) setSelection(selected, null);
      return true;
    }

    map.on("zoomend", () => geoLayer.setStyle(styleFn));
    map.on("click", () => { if (selected) setSelection(selected, null); });

    // ── zone search (same behaviour as the epidemic dashboard's #zone-search) ──
    const input = root.querySelector(".zs-input"), results = root.querySelector(".zs-results");
    const searchIndex = () => visibleZones.map((f) => ({ nom: f.properties.nom, prov: f.properties.province, hay: normKey(`${f.properties.nom} ${f.properties.province}`) }))
      .sort((a, b) => a.nom.localeCompare(b.nom, "fr"));
    let matches = [], active = -1;
    const closeResults = () => { results.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; };
    const pick = (m) => {
      closeResults();
      input.value = m.nom;
      geoLayer.eachLayer((l) => {
        if (l.feature.properties.nom === m.nom) {
          map.fitBounds(l.getBounds(), { padding: [60, 60], maxZoom: 9 });
          if (selected !== m.nom) setSelection(m.nom, m.prov);
        }
      });
    };
    const drawResults = () => {
      results.innerHTML = matches.map((m, i) => `<div role="option" class="zs-item${i === active ? " active" : ""}" data-i="${i}">${esc(m.nom)} <span>${esc(m.prov)}</span></div>`).join("")
        || '<div class="zs-empty">Aucune zone de santé trouvée</div>';
      results.querySelectorAll(".zs-item").forEach((el) => el.addEventListener("mousedown", (e) => { e.preventDefault(); pick(matches[+el.dataset.i]); }));
    };
    input.addEventListener("input", () => {
      const q = normKey(input.value);
      if (!q) { closeResults(); return; }
      matches = searchIndex().filter((z) => z.hay.includes(q)).slice(0, 12);
      active = matches.length ? 0 : -1;
      results.hidden = false; input.setAttribute("aria-expanded", "true");
      drawResults();
    });
    input.addEventListener("keydown", (e) => {
      if (results.hidden) return;
      if (e.key === "ArrowDown") { active = Math.min(matches.length - 1, active + 1); drawResults(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = Math.max(0, active - 1); drawResults(); e.preventDefault(); }
      else if (e.key === "Enter" && matches[active]) { pick(matches[active]); e.preventDefault(); }
      else if (e.key === "Escape") closeResults();
    });
    input.addEventListener("blur", () => setTimeout(closeResults, 120));
    L.DomEvent.disableClickPropagation(root.querySelector(".m-controls"));
    L.DomEvent.disableScrollPropagation(root.querySelector(".m-controls"));
    L.DomEvent.disableClickPropagation(root.querySelector(".m-info"));
    L.DomEvent.disableScrollPropagation(root.querySelector(".m-info"));

    function recompute() {
      const layer = layerDef();
      if (layer.categorical) domain = { categorical: true };
      else if (layer.domain) domain = { min: layer.domain[0], max: layer.domain[1], isLog: false };
      else {
        const vals = [];
        visibleZones.forEach((f) => {
          const z = zoneValue(layer, f.properties.nom, f.properties.province, D);
          if (z.state === "value") vals.push(z.v);
        });
        let lo = vals.length ? Math.min(...vals) : 1, hi = vals.length ? Math.max(...vals) : 10;
        if (hi === lo) hi = lo * 10;
        domain = { min: lo, max: hi, isLog: layer.scale === "log" };
      }
      geoLayer.setStyle(styleFn);
      updateLegend(layer);
      updateMeta(layer);
    }

    function updateLegend(layer) {
      const q = (sel) => root.querySelector(sel);
      q(".m-legend-title").innerHTML = `<strong>${esc(layer.label)}</strong>`;
      const gray = [];
      if (layer.categorical) {
        q(".legend-bar").style.display = q(".legend-ticks").style.display = q(".legend-scale").style.display = "none";
        q(".legend-cats").innerHTML = Object.keys(STATUS_HEX).map((k) => `<div><span class="swatch" style="background:${STATUS_HEX[k]}"></span>${esc(STATUS_LABELS[k])}</div>`).join("");
        gray.push(`<span class="swatch" style="background:${ZERO_FILL}"></span>Aucun cas rapporté`);
      } else {
        q(".legend-bar").style.display = q(".legend-ticks").style.display = q(".legend-scale").style.display = "";
        q(".legend-cats").innerHTML = "";
        const stops = [];
        for (let i = 0; i < 32; i++) { const t = i / 31; stops.push(`${rgbStr(lerpColor(layer.palette, t))} ${Math.round(t * 100)}%`); }
        q(".legend-bar").style.background = `linear-gradient(to right, ${stops.join(", ")})`;
        const mid = domain.isLog ? Math.sqrt(domain.min * domain.max) : (domain.min + domain.max) / 2;
        q(".legend-ticks").innerHTML = [domain.min, mid, domain.max].map((v) => `<span>${fmtVal(v, layer)}</span>`).join("");
        q(".legend-scale").textContent = domain.isLog ? "(échelle logarithmique)" : "(échelle linéaire)";
        if (!layer.domain) gray.push(`<span class="swatch" style="background:${ZERO_FILL}"></span>${esc(layer.zero || "0")}`);
      }
      gray.push('<span class="swatch swatch-dashed"></span>Non extrait / non rapporté');
      gray.push('<span class="swatch swatch-no-data"></span>Présentation non reçue');
      q(".legend-gray").innerHTML = gray.join(" · ");
    }

    function updateMeta(layer) {
      const provs = Object.keys(D.summary);
      const withTable = provs.filter((p) => D.cov[p] && D.cov[p].ok.includes(layer.kind) && (!layer.needs || (D.has[layer.needs] && D.has[layer.needs].has(p))));
      root.querySelector(".m-meta").innerHTML =
        `Présentations provinciales du ${esc(frDate(DATE))} · ${withTable.length}/${provs.length} province(s) rapportent cet indicateur.`
        + `<br>Zones de santé : shapefile GRID3 (BDBV2026-Data).`;
    }

    layerSelect.addEventListener("change", recompute);

    const toLL = (bb) => L.latLngBounds([bb[1], bb[0]], [bb[3], bb[2]]);
    function focusBounds(provs) {
      let b = null;
      provs.forEach((p) => {
        const bb = G.bounds[p];
        if (!bb) return;
        const lb = L.latLngBounds([bb[1], bb[0]], [bb[3], bb[2]]);
        b = b ? b.extend(lb) : lb;
      });
      return b;
    }

    return {
      root,
      update(opts) {
        D = mapData();
        // a province view (province page, or one province chosen) is cropped
        // to that province; anything else shows the whole DRC
        const crop = !!opts.crop && (opts.focus || []).some((p) => G.bounds[p]);
        focusProvs = crop ? opts.focus.filter((p) => G.bounds[p]) : Object.keys(G.bounds);
        highlightProvs = opts.highlight || [];
        const changed = setScope(crop ? "province" : "country", crop ? focusProvs : []);
        outlineLayer.setStyle(outlineStyle);
        if (changed) {
          const target = crop ? focusBounds(focusProvs)
            : (C && C.bounds ? toLL(C.bounds) : focusBounds(focusProvs));
          if (target) {
            // leave room for the floating panels (Couche left, Zone right) on wide screens
            const w = root.clientWidth;
            const side = full && w > 1000 ? 340 : w > 900 ? 120 : 20;
            // keep the user on the DRC (or on the province): no panning or
            // zooming out to the rest of Africa
            if (map.setMaxBounds) { map.setMaxBounds(null); map.setMinZoom(0); }
            map.fitBounds(target, { paddingTopLeft: [side, 30], paddingBottomRight: [side, 30], animate: false });
            if (map.setMaxBounds) {
              const lock = target.pad(crop ? 0.25 : 0.12);
              map.setMaxBounds(lock);
              map.setMinZoom(Math.max(0, map.getBoundsZoom(lock) - 0.5));
            }
          }
        }
        recompute();
        if (selected) {
          const f = G.zones.features.find((x) => x.properties.nom === selected);
          if (f) infoBody.innerHTML = infoHTML(selected, f.properties.province);
        }
        setTimeout(() => map.invalidateSize(), 0);
      },
    };
  }

  // ── Header tracker (same role as the epidemic dashboard's #tracker) ──
  // cumul repris de la carte de synthèse quand le tableau par ZS manque (voir payload.completer_totaux)
  const carteCell = (r, k) => (!isNum(r[k]) ? "–" : r.source_cumul
    ? `<span class="src-tip" title="${esc("Repris de la " + r.source_cumul)}">${fmt(r[k])}</span><span class="kpi-frac">carte</span>`
    : fmt(r[k]));

  function renderTracker() {
    const el = document.getElementById("tracker");
    if (!el) return;
    const rows = atDate(P.summary, DATE);
    if (!rows.length) { el.innerHTML = ""; return; }
    const n = (k) => rows.filter((r) => isNum(r[k])).length;
    const conf = sum(rows, "cumul_confirmes"), dec = sum(rows, "cumul_deces");
    const aS = sum(rows, "contacts_a_suivre"), vus = sum(rows, "contacts_vus");
    const cell = (cls, v, label, sub) => `<div class="t-cell ${cls}"><div class="num">${v}</div><div class="lbl">${esc(label)}</div><div class="cov">${esc(sub)}</div></div>`;
    el.innerHTML = `<div class="t-title">Présentations du ${esc(frDate(DATE))}</div><div class="t-row">`
      + cell("cases", fmt(conf), "Confirmés (cumul)", `${n("cumul_confirmes")}/${rows.length} prov.`)
      + cell("deaths", fmt(dec), "Décès (cumul)", `létalité ${fmtPct(pct(dec, conf))}`)
      + cell("alerts", fmt(sum(rows, "nouvelles_alertes")), "Nouvelles alertes", `${n("nouvelles_alertes")}/${rows.length} prov.`)
      + cell("contacts", fmtPct(pct(vus, aS)), "Contacts suivis", `${fmt(aS)} à suivre`)
      + "</div>";
  }

  function renderSnapshot() {
    mapView(document.getElementById("map-root"), { focus: atDate(P.summary, DATE).map((r) => r.province) });
  }

  // ════════════════════════════════════════════════════════════
  // Pages
  // ════════════════════════════════════════════════════════════

  function renderOverview() {
    const rows = atDate(P.summary, DATE);
    const prev = prevDate(DATE);
    const prevRows = prev ? atDate(P.summary, prev) : [];
    const note = document.getElementById("coverage-note");
    const msg = missingSentence(DATE);
    note.innerHTML = msg;
    note.classList.toggle("show", !!msg);

    const withVal = (key) => rows.filter((r) => isNum(r[key]));
    const deltaFor = (key) => {
      if (!prev) return "";
      const provs = withVal(key).map((r) => r.province).filter((p) => prevRows.some((q) => q.province === p && isNum(q[key])));
      if (!provs.length) return "";
      const now = sum(rows.filter((r) => provs.includes(r.province)), key);
      const before = sum(prevRows.filter((r) => provs.includes(r.province)), key);
      const d = Math.round(now - before);
      return `${d > 0 ? "+" : ""}${fmt(d)} depuis le ${shortDate(prev)} (mêmes provinces)`;
    };
    const conf = sum(rows, "cumul_confirmes"), dec = sum(rows, "cumul_deces");
    const aSuivre = sum(rows, "contacts_a_suivre"), vus = sum(rows, "contacts_vus");
    const nProv = rows.length;
    const kpis = [
      { label: "Cumul des confirmés", value: fmt(conf), sub: `${withVal("cumul_confirmes").length}/${nProv} provinces`, delta: deltaFor("cumul_confirmes") },
      { label: "Cumul des décès", value: fmt(dec), sub: `Létalité ${fmtPct(pct(dec, conf))}`, delta: deltaFor("cumul_deces") },
      { label: "Confirmés · 21 jours", value: fmt(sum(rows, "confirmes_21j")), sub: `${withVal("confirmes_21j").length}/${nProv} provinces le rapportent`, delta: deltaFor("confirmes_21j") },
      { label: "Nouvelles alertes", value: fmt(sum(rows, "nouvelles_alertes")), sub: `${fmt(sum(rows, "alertes_validees"))} validées · ${withVal("nouvelles_alertes").length}/${nProv} provinces`, delta: deltaFor("nouvelles_alertes") },
      { label: "Contacts à suivre", value: fmt(aSuivre), sub: `${fmtPct(pct(vus, aSuivre))} vus · ${withVal("contacts_a_suivre").length}/${nProv} provinces`, delta: deltaFor("contacts_a_suivre") },
    ];
    document.getElementById("kpis").innerHTML = kpis.map((k) =>
      `<div class="kpi"><div class="label">${esc(k.label)}</div><div class="value">${k.value}</div><div class="sub">${esc(k.sub)}</div>${k.delta ? `<div class="delta">${esc(k.delta)}</div>` : ""}</div>`).join("");

    const byCases = rows.slice().sort((a, b) => (b.cumul_confirmes ?? -1) - (a.cumul_confirmes ?? -1));
    hbarChart(document.getElementById("chart-province-cases"), byCases.map((r) => ({
      label: r.province, value: r.cumul_confirmes,
      tip: [["Confirmés", fmt(r.cumul_confirmes)], ["Décès", fmt(r.cumul_deces)], ["Létalité", fmtPct(r.letalite_pct)], ["ZS affectées", fmt(r.zs_affectees)]],
    })), { aria: "Cumul des cas confirmés par province" });

    const byFollow = rows.slice().sort((a, b) => (b.taux_suivi_pct ?? -1) - (a.taux_suivi_pct ?? -1));
    hbarChart(document.getElementById("chart-province-followup"), byFollow.map((r) => ({
      label: r.province, value: r.taux_suivi_pct,
      tip: [["Taux de suivi", fmtPct(r.taux_suivi_pct)], ["Contacts vus", fmt(r.contacts_vus)], ["À suivre", fmt(r.contacts_a_suivre)], ["Devenus suspects", fmt(r.contacts_devenus_suspects)]],
    })), { format: fmtPct, max: 100, aria: "Taux de suivi des contacts par province" });

    const cov = Object.fromEntries(coverage(DATE).map((c) => [c.province, c]));
    const tablesCell = (r) => {
      const c = cov[r.province];
      if (!c) return "–";
      return ["cases", "alerts", "contacts"].map((k) => c.ok.includes(k) ? pill("good", "✓", TABLE_LABELS[k]) : pill(c.image[k] ? "warn" : "crit", c.image[k] ? "!" : "✕", TABLE_LABELS[k] + (c.image[k] ? " (image)" : ""))).join(" ");
    };
    renderTable(document.getElementById("table-provinces"), [
      { key: "province", label: "Province", render: (r) => (r.cumul_confirmes === undefined ? esc(r.province) : provLink(r.province)) },
      { key: "tables", label: "Tableaux extraits", sortable: false, cls: "pills", render: tablesCell },
      { key: "cumul_confirmes", label: "Confirmés", num: true, render: (r) => carteCell(r, "cumul_confirmes") },
      { key: "cumul_deces", label: "Décès", num: true, render: (r) => carteCell(r, "cumul_deces") },
      { key: "letalite_pct", label: "Létalité", num: true, fmt: fmtPct },
      { key: "confirmes_21j", label: "Confirmés 21 j", num: true, fmt },
      { key: "zs_affectees", label: "ZS affectées", num: true, fmt },
      { key: "nouvelles_alertes", label: "Nouvelles alertes", num: true, fmt },
      { key: "alertes_validees", label: "Alertes validées", num: true, fmt },
      { key: "contacts_a_suivre", label: "Contacts à suivre", num: true, fmt },
      { key: "taux_suivi_pct", label: "Taux de suivi", num: true, fmt: fmtPct },
    ], rows, {
      sortKey: "cumul_confirmes",
      total: {
        province: "Total (extrait)", cumul_confirmes: conf, cumul_deces: dec, letalite_pct: pct(dec, conf),
        confirmes_21j: sum(rows, "confirmes_21j"), zs_affectees: sum(rows, "zs_affectees"),
        nouvelles_alertes: sum(rows, "nouvelles_alertes"), alertes_validees: sum(rows, "alertes_validees"),
        contacts_a_suivre: aSuivre, taux_suivi_pct: pct(vus, aSuivre), tables: "",
      },
    });
  }

  let getZoneProvince = () => "";
  function zoneStatus(r) {
    const j = r.jours_depuis_dernier_cas;
    if (!isNum(j)) return '<span class="na">–</span>';
    if (j <= 21) return pill("crit", "●", "Active");
    if (j <= 42) return pill("warn", "!", "Surveillance");
    return pill("good", "✓", "Sans cas > 42 j");
  }
  function renderZones() {
    const prov = getZoneProvince();
    const rows = atDate(P.cases, DATE).filter((r) => !prov || r.province === prov);
    mapView(document.getElementById("map-root"), { focus: prov ? [prov] : atDate(P.summary, DATE).map((r) => r.province), highlight: prov ? [prov] : [], crop: !!prov });
    const multi = !prov;
    const zlabel = (r) => (multi ? `${r.zone} (${r.province})` : r.zone);
    const active = rows.filter((r) => isNum(r.confirmes_21j) && r.confirmes_21j > 0).sort((a, b) => b.confirmes_21j - a.confirmes_21j).slice(0, 25);
    const no21 = rows.length && !rows.some((r) => isNum(r.confirmes_21j));
    hbarChart(document.getElementById("chart-zones-21"), active.map((r) => ({
      label: zlabel(r), value: r.confirmes_21j,
      tip: [["Province", esc(r.province)], ["Confirmés 21 j", fmt(r.confirmes_21j)], ["Décès 21 j", fmt(r.deces_21j)], ["Dernier cas", frDate(r.date_dernier_cas)]],
    })), { empty: no21 ? "Le tableau des cas de cette province ne donne pas les confirmés sur 21 jours." : "Aucune zone avec des cas confirmés sur les 21 derniers jours.", aria: "Confirmés sur 21 jours par zone de santé" });
    renderTable(document.getElementById("table-zones"), [
      { key: "zone", label: "Zone de santé", render: (r) => esc(r.zone) + (r.zone_resolved === false ? ' <span title="Nom non reconnu dans le référentiel des ZS">⚠</span>' : "") },
      { key: "province", label: "Province" },
      { key: "cumul_confirmes", label: "Confirmés", num: true, fmt },
      { key: "cumul_deces", label: "Décès", num: true, fmt },
      { key: "letalite", label: "Létalité", num: true, fmt: fmtPct },
      { key: "confirmes_21j", label: "Confirmés 21 j", num: true, fmt },
      { key: "deces_21j", label: "Décès 21 j", num: true, fmt },
      { key: "date_dernier_cas", label: "Dernier cas", render: (r) => (r.date_dernier_cas ? esc(frDate(r.date_dernier_cas)) : '<span class="na">–</span>') },
      { key: "jours_depuis_dernier_cas", label: "Jours depuis", num: true, fmt },
      { key: "statut", label: "Statut", sortValue: (r) => r.jours_depuis_dernier_cas, render: zoneStatus },
    ], rows, { sortKey: "cumul_confirmes", empty: "Aucun tableau des cas extrait pour cette date." });
  }

  const METRICS = [
    { key: "cumul_confirmes", label: "Cumul des cas confirmés" },
    { key: "cumul_deces", label: "Cumul des décès" },
    { key: "confirmes_21j", label: "Confirmés sur 21 jours" },
    { key: "nouvelles_alertes", label: "Nouvelles alertes" },
    { key: "alertes_validees", label: "Alertes validées" },
    { key: "contacts_a_suivre", label: "Contacts à suivre" },
    { key: "taux_suivi_pct", label: "Taux de suivi des contacts", pct: true },
  ];
  function renderTrends() {
    const sel = document.getElementById("metric-select");
    if (!sel.options.length) {
      sel.innerHTML = METRICS.map((m) => `<option value="${m.key}">${esc(m.label)}</option>`).join("");
      sel.addEventListener("change", renderTrends);
    }
    const metric = METRICS.find((m) => m.key === sel.value) || METRICS[0];
    const fmtV = metric.pct ? fmtPct : fmt;
    const national = DATES.map((d) => {
      const rows = atDate(P.summary, d);
      const contributing = rows.filter((r) => isNum(r[metric.key]));
      const value = metric.pct ? pct(sum(rows, "contacts_vus"), sum(rows, "contacts_a_suivre")) : sum(rows, metric.key);
      return { date: d, value, extra: [["Provinces incluses", `${contributing.length}/${rows.length}`]] };
    });
    document.getElementById("national-title").textContent = `${metric.label} — ensemble des provinces extraites`;
    lineChart(document.getElementById("chart-national"), national, { format: fmtV, label: metric.label, pct: metric.pct, max: metric.pct ? 100 : null, height: 220, aria: metric.label });
    const wrap = document.getElementById("chart-multiples");
    wrap.innerHTML = "";
    (META.provinces || []).forEach((prov) => {
      const card = document.createElement("article");
      card.className = "card";
      card.innerHTML = `<header class="card-head"><h3>${esc(prov)}</h3></header><div class="chart"></div>`;
      wrap.appendChild(card);
      const pts = DATES.map((d) => {
        const r = (P.summary || []).find((s) => s.date === d && s.province === prov);
        return { date: d, value: r ? r[metric.key] : null };
      });
      lineChart(card.querySelector(".chart"), pts, { format: fmtV, label: metric.label, pct: metric.pct, max: metric.pct ? 100 : null, empty: "Indicateur non extrait pour cette province.", aria: `${metric.label}, ${prov}` });
    });
  }

  let getAlertProvince = () => "";
  function renderAlerts() {
    const prov = getAlertProvince();
    const keep = (r) => !prov || r.province === prov;

    const src = atDate(P.sources, DATE).filter(keep);
    const provs = [...new Set(src.map((r) => r.province))].sort();
    const stackRows = provs.map((p) => ({ label: p, parts: Object.fromEntries(src.filter((r) => r.province === p).map((r) => [r.source, r.total || 0])) }));
    stackedChart(document.getElementById("chart-sources"), stackRows, SOURCE_ORDER, SOURCE_LABELS, { empty: "Aucun tableau des sources extrait.", aria: "Sources des alertes par province" });
    renderTable(document.getElementById("table-sources"), [
      { key: "province", label: "Province" },
      { key: "source", label: "Source", render: (r) => esc(SOURCE_LABELS[r.source] || r.source) },
      { key: "vivants", label: "Vivants", num: true, fmt },
      { key: "deces", label: "Décès", num: true, fmt },
      { key: "total", label: "Total", num: true, fmt },
    ], src, { sortKey: "total" });

    const contacts = atDate(P.contacts, DATE).filter(keep);
    let bullets;
    if (prov) {
      bullets = contacts.filter((r) => isNum(r.a_suivre) && r.a_suivre > 0).sort((a, b) => b.a_suivre - a.a_suivre).map((r) => ({ label: r.zone, total: r.a_suivre, part: r.vus }));
    } else {
      bullets = atDate(P.summary, DATE).filter((r) => isNum(r.contacts_a_suivre)).sort((a, b) => b.contacts_a_suivre - a.contacts_a_suivre).map((r) => ({ label: r.province, total: r.contacts_a_suivre, part: r.contacts_vus }));
    }
    bulletChart(document.getElementById("chart-contacts"), bullets, { totalLabel: "À suivre", partLabel: "Vus", empty: "Aucun tableau de contacts extrait.", aria: "Contacts à suivre et vus" });

    const zoneAlerts = atDate(P.alerts_zone, DATE).filter(keep);
    const zoneProvs = new Set(zoneAlerts.map((r) => r.province));
    const aireAlerts = atDate(P.alerts_aire, DATE).filter(keep).filter((r) => !zoneProvs.has(r.province));
    const alertRows = zoneAlerts.map((r) => ({ ...r, niveau: "ZS", lieu: r.zone }))
      .concat(aireAlerts.map((r) => ({ ...r, niveau: "AS", lieu: r.aire_sante + (r.zone ? ` (${r.zone})` : "") })));
    const validees = (r) => (isNum(r.validees_vivants) || isNum(r.validees_deces) ? (r.validees_vivants || 0) + (r.validees_deces || 0) : null);
    const nouvelles = (r) => (isNum(r.nouvelles_alertes_vivants) || isNum(r.nouvelles_alertes_deces) ? (r.nouvelles_alertes_vivants || 0) + (r.nouvelles_alertes_deces || 0) : null);
    renderTable(document.getElementById("table-alerts"), [
      { key: "lieu", label: "Zone / aire de santé" },
      { key: "niveau", label: "Niveau" },
      { key: "province", label: "Province" },
      { key: "nouvelles", label: "Nouvelles", num: true, sortValue: nouvelles, render: (r) => fmt(nouvelles(r)) },
      { key: "nouvelles_alertes_deces", label: "dont décès", num: true, fmt },
      { key: "total_alertes", label: "Total alertes", num: true, fmt },
      { key: "validees", label: "Validées", num: true, sortValue: validees, render: (r) => fmt(validees(r)) },
      { key: "invalidees_vivants", label: "Invalidées", num: true, fmt },
    ], alertRows.filter((r) => isNum(r.total_alertes) || isNum(nouvelles(r))), { sortKey: "total_alertes", empty: "Aucun tableau d'alertes extrait pour cette sélection." });

    renderTable(document.getElementById("table-contacts"), [
      { key: "zone", label: "Zone de santé" },
      { key: "province", label: "Province" },
      { key: "a_suivre", label: "À suivre", num: true, fmt },
      { key: "vus", label: "Vus", num: true, fmt },
      { key: "taux", label: "Taux de suivi", num: true, sortValue: (r) => pct(r.vus, r.a_suivre), render: (r) => fmtPct(pct(r.vus, r.a_suivre) ?? r.taux_suivi_pct) },
      { key: "nouveaux", label: "Nouveaux", num: true, fmt },
      { key: "devenus_suspects", label: "Devenus suspects", num: true, fmt },
      { key: "perdus_de_vue", label: "Perdus de vue", num: true, fmt },
      { key: "jamais_vus", label: "Jamais vus", num: true, fmt },
    ], contacts.filter((r) => (r.a_suivre || 0) > 0 || (r.vus || 0) > 0), { sortKey: "a_suivre", empty: "Aucun tableau de contacts extrait pour cette sélection." });
  }

  const CHECK_LABELS = {
    extraction: "Présentation illisible / province inconnue",
    table_absente_cases: "Tableau des cas absent",
    table_absente_alerts: "Tableau des alertes absent",
    table_absente_contacts: "Tableau des contacts absent",
    extraction_cases: "Extraction des cas", extraction_alerts: "Extraction des alertes",
    extraction_contacts: "Extraction des contacts", extraction_date: "Date de la présentation",
    total_incoherent_cases: "Total des cas incohérent", total_incoherent_alerts: "Total des alertes incohérent",
    total_incoherent_contacts: "Total des contacts incohérent",
    jours_depuis_incoherent: "« Jours depuis » incohérent",
    deces_sup_confirmes: "Décès > confirmés", "21j_sup_cumul": "21 j > cumul",
    deces_sup_confirmes_21j: "Décès 21 j > confirmés 21 j",
    contacts_vus_sup_a_suivre: "Contacts vus > à suivre",
    cumul_en_baisse: "Cumul en baisse", province_absente: "Province absente",
    valeur_negative: "Valeur négative", date_dernier_cas_future: "Dernier cas dans le futur",
  };
  function renderQuality() {
    const cov = coverage(DATE);
    const received = new Set(cov.map((c) => c.province));
    const all = META.provinces || [];
    const kinds = ["cases", "alerts", "contacts", "alert_sources"];
    const covRows = all.map((p) => ({ province: p, c: cov.find((x) => x.province === p) }));
    renderTable(document.getElementById("coverage-matrix"), [
      { key: "province", label: "Province" },
      { key: "recu", label: "Présentation", sortable: false, render: (r) => (received.has(r.province) ? pill("good", "✓", "Reçue") : pill("neutral", "–", "Non reçue")) },
    ].concat(kinds.map((k) => ({
      key: k, label: TABLE_LABELS[k], sortable: false,
      render: (r) => {
        if (!r.c) return '<span class="na">–</span>';
        if (r.c.ok.includes(k)) return pill("good", "✓", "Extrait");
        if (k === "alert_sources") return pill("neutral", "–", "Non trouvé");
        return r.c.image[k] ? pill("warn", "!", "Image") : pill("crit", "✕", "Absent");
      },
    }))), covRows, { sortKey: "province", desc: false, empty: "Aucune présentation." });

    const lvlSel = document.getElementById("level-select");
    if (!lvlSel.dataset.bound) { lvlSel.dataset.bound = "1"; lvlSel.addEventListener("change", renderQuality); }
    const lvl = lvlSel.value;
    const qa = atDate(P.qa, DATE).filter((q) => !lvl || q.status === lvl);
    renderTable(document.getElementById("table-qa"), [
      { key: "province", label: "Province" },
      { key: "status", label: "Niveau", render: (q) => (q.status === "fail" ? pill("crit", "✕", "Bloquant") : pill("warn", "!", "Avertissement")) },
      { key: "check", label: "Contrôle", render: (q) => esc(CHECK_LABELS[q.check] || q.check) },
      { key: "detail", label: "Détail", cls: "detail", sortable: false },
    ], qa, { sortKey: "province", desc: false, empty: "Aucun constat pour cette date." });
  }


  // ── Résumé par province (province-<slug>.html) ────────────
  const plural = (n, one, many) => `${fmt(n)} ${n > 1 ? many : one}`;
  const signed = (d) => (d > 0 ? `+${fmt(d)}` : d < 0 ? `−${fmt(-d)}` : "aucune variation");

  function provinceSummaryHTML(prov, s, ps, prevD, cases, alerts, contacts, sources, cov, qa) {
    const out = [];
    if (!s) return `<p>Aucune présentation de <strong>${esc(prov)}</strong> n'a été reçue pour le ${frDate(DATE)}.</p>`;
    if (cov && !cov.ok.length) {
      const img = cov.missing.some((k) => cov.image[k]);
      return `<p>La présentation du <strong>${frDate(DATE)}</strong> a été reçue, mais <strong>aucun tableau n'a pu être lu</strong>${img ? " : les tableaux y sont collés en image" : ""}.</p>` +
        `<p>Les chiffres de ${esc(prov)} pour cette date doivent être consultés directement dans la présentation${img ? ", ou la DPS doit renvoyer des tableaux PowerPoint natifs" : ""}.</p>`;
    }

    // cases
    if (isNum(s.cumul_confirmes)) {
      let t = `Au <strong>${frDate(DATE)}</strong>, la province rapporte <strong>${plural(s.cumul_confirmes, "cas confirmé", "cas confirmés")}</strong> au cumul et <strong>${plural(s.cumul_deces || 0, "décès", "décès")}</strong> (létalité ${fmtPct(s.letalite_pct)})`
        + (s.source_cumul ? `, chiffres lus sur la carte de synthèse de la présentation : le tableau des cas par zone de santé est absent ou collé en image ce jour-là.`
          : `, répartis sur ${plural(s.zs_affectees || 0, "zone de santé", "zones de santé")}.`);
      if (ps && isNum(ps.cumul_confirmes)) {
        const dc = s.cumul_confirmes - ps.cumul_confirmes, dd = (s.cumul_deces || 0) - (ps.cumul_deces || 0);
        const part = (d, one, many) => (d > 0 ? `+${plural(d, one, many)}` : d < 0 ? `${plural(-d, one, many)} en moins (correction ?)` : "");
        const bits = [part(dc, "cas confirmé", "cas confirmés"), part(dd, "décès", "décès")].filter(Boolean);
        t += bits.length
          ? ` Depuis le ${frDate(prevD)} : ${bits.join(", ")}.`
          : ` Pas de nouveau cas confirmé ni de nouveau décès depuis le ${frDate(prevD)}.`;
      }
      out.push(t);
    } else {
      out.push(`Le tableau des cas confirmés n'a pas pu être extrait de la présentation du ${frDate(DATE)}${cov && cov.image.cases ? " (tableau collé en image)" : ""}.`);
    }

    // last 21 days
    const with21 = cases.filter((r) => isNum(r.confirmes_21j));
    if (with21.length) {
      const active = cases.filter((r) => isNum(r.jours_depuis_dernier_cas) ? r.jours_depuis_dernier_cas <= 21 : (r.confirmes_21j || 0) > 0);
      let t = `Sur les 21 derniers jours : <strong>${plural(s.confirmes_21j || 0, "confirmé", "confirmés")}</strong> et ${plural(s.deces_21j || 0, "décès", "décès")}`;
      t += `, ${plural(active.length, "zone de santé active", "zones de santé actives")} (dernier cas il y a 21 jours au plus).`;
      const top = with21.slice().sort((a, b) => b.confirmes_21j - a.confirmes_21j)[0];
      if (top && top.confirmes_21j > 0 && s.confirmes_21j) {
        t += ` La plus touchée est <strong>${esc(top.zone)}</strong> (${fmt(top.confirmes_21j)}, soit ${fmtPct(pct(top.confirmes_21j, s.confirmes_21j))} des cas récents).`;
      }
      const quiet = cases.filter((r) => isNum(r.jours_depuis_dernier_cas) && r.jours_depuis_dernier_cas > 42);
      if (quiet.length) t += ` ${plural(quiet.length, "zone n'a", "zones n'ont")} plus de cas depuis plus de 42 jours.`;
      out.push(t);
    } else if (cases.length) {
      out.push("La présentation ne donne pas les cas des 21 derniers jours par zone de santé.");
    }

    // alerts
    if (isNum(s.nouvelles_alertes) || isNum(s.total_alertes)) {
      let t = `<strong>${plural(s.nouvelles_alertes || 0, "nouvelle alerte", "nouvelles alertes")}</strong> reçues`;
      if (isNum(s.alertes_validees)) t += `, dont ${plural(s.alertes_validees, "validée", "validées")} comme cas suspect (${fmtPct(pct(s.alertes_validees, s.total_alertes || s.nouvelles_alertes))} du total des alertes)`;
      t += ".";
      const tot = sources.reduce((a, r) => a + (r.total || 0), 0);
      const main = sources.slice().sort((a, b) => (b.total || 0) - (a.total || 0))[0];
      if (main && tot) t += ` Principale source : ${esc(SOURCE_LABELS[main.source] || main.source)} (${fmtPct(pct(main.total, tot))}).`;
      out.push(t);
    } else {
      out.push(`Le tableau des alertes n'a pas pu être extrait${cov && cov.image.alerts ? " (tableau collé en image)" : ""}.`);
    }

    // contacts
    if (isNum(s.contacts_a_suivre)) {
      let t = `<strong>${plural(s.contacts_a_suivre, "contact", "contacts")}</strong> à suivre, ${fmt(s.contacts_vus)} vus (taux de suivi ${fmtPct(s.taux_suivi_pct)})`;
      if (s.contacts_devenus_suspects) t += ` ; ${plural(s.contacts_devenus_suspects, "contact est devenu suspect", "contacts sont devenus suspects")}`;
      t += ".";
      // 0 vu with contacts to follow is almost always "data not sent", not a 0 % follow-up
      const noData = contacts.filter((r) => (r.a_suivre || 0) > 0 && r.vus === 0).map((r) => esc(r.zone));
      const weak = contacts.filter((r) => (r.a_suivre || 0) >= 50 && (r.vus || 0) > 0)
        .map((r) => ({ zone: r.zone, rate: Math.round(pct(r.vus, r.a_suivre) * 10) / 10 }))
        .filter((r) => r.rate < 80).sort((a, b) => a.rate - b.rate);
      if (weak.length) t += ` Suivi le plus faible : ${weak.slice(0, 3).map((w) => `${esc(w.zone)} (${fmtPct(w.rate)})`).join(", ")}.`;
      if (noData.length) t += ` Aucun contact vu déclaré pour ${noData.join(", ")} : données de suivi probablement non transmises.`;
      out.push(t);
    } else {
      out.push(`Le tableau de suivi des contacts n'a pas pu être extrait${cov && cov.image.contacts ? " (tableau collé en image)" : ""}.`);
    }

    // data quality
    const incoh = qa.filter((q) => !q.check.startsWith("table_absente"));
    if (incoh.length) out.push(`${plural(incoh.length, "incohérence a été relevée", "incohérences ont été relevées")} dans la présentation : voir « Qualité des données » en bas de page.`);
    return out.map((t) => `<p>${t}</p>`).join("");
  }

  function renderProvince() {
    const prov = document.body.dataset.province;
    const s = atDate(P.summary, DATE).find((r) => r.province === prov);
    const prevD = prevDate(DATE);
    const ps = prevD ? atDate(P.summary, prevD).find((r) => r.province === prov) : null;
    const mine = (rows) => atDate(rows, DATE).filter((r) => r.province === prov);
    const cases = mine(P.cases), contacts = mine(P.contacts), sources = mine(P.sources);
    const zoneAlerts = mine(P.alerts_zone), aireAlerts = mine(P.alerts_aire);
    const qa = mine(P.qa);
    const cov = coverage(DATE).find((c) => c.province === prov);

    mapView(document.getElementById("map-root"), { focus: [prov], highlight: [prov], crop: true });
    document.getElementById("prov-summary").innerHTML = provinceSummaryHTML(prov, s, ps, prevD, cases, zoneAlerts.length ? zoneAlerts : aireAlerts, contacts, sources, cov, qa);

    const delta = (key) => {
      if (!s || !ps || !isNum(s[key]) || !isNum(ps[key])) return "";
      return `${signed(Math.round(s[key] - ps[key]))} depuis le ${shortDate(prevD)}`;
    };
    const kpis = s ? [
      { label: "Cumul des confirmés", value: fmt(s.cumul_confirmes), sub: `${fmt(s.zs_affectees)} ZS affectées`, delta: delta("cumul_confirmes") },
      { label: "Cumul des décès", value: fmt(s.cumul_deces), sub: `Létalité ${fmtPct(s.letalite_pct)}`, delta: delta("cumul_deces") },
      { label: "Confirmés · 21 jours", value: fmt(s.confirmes_21j), sub: isNum(s.zs_actives_21j) ? `${fmt(s.zs_actives_21j)} ZS actives` : "non rapporté", delta: delta("confirmes_21j") },
      { label: "Nouvelles alertes", value: fmt(s.nouvelles_alertes), sub: `${fmt(s.alertes_validees)} validées`, delta: delta("nouvelles_alertes") },
      { label: "Contacts à suivre", value: fmt(s.contacts_a_suivre), sub: `${fmtPct(s.taux_suivi_pct)} vus`, delta: delta("contacts_a_suivre") },
    ] : [];
    document.getElementById("kpis").innerHTML = kpis.map((k) =>
      `<div class="kpi"><div class="label">${esc(k.label)}</div><div class="value">${k.value}</div><div class="sub">${esc(k.sub)}</div>${k.delta ? `<div class="delta">${esc(k.delta)}</div>` : ""}</div>`).join("");

    // zones chart: 21 days when available, otherwise cumulative
    const has21 = cases.some((r) => isNum(r.confirmes_21j));
    const key = has21 ? "confirmes_21j" : "cumul_confirmes";
    document.getElementById("zones-chart-title").textContent = has21
      ? "Confirmés sur les 21 derniers jours, par zone de santé"
      : "Cumul des cas confirmés, par zone de santé";
    hbarChart(document.getElementById("chart-zones"), cases.filter((r) => isNum(r[key]) && r[key] > 0).sort((a, b) => b[key] - a[key]).slice(0, 25).map((r) => ({
      label: r.zone, value: r[key],
      tip: [["Confirmés (cumul)", fmt(r.cumul_confirmes)], ["Décès (cumul)", fmt(r.cumul_deces)], ["Confirmés 21 j", fmt(r.confirmes_21j)], ["Dernier cas", frDate(r.date_dernier_cas)]],
    })), { empty: "Aucun tableau des cas extrait pour cette date.", aria: "Cas par zone de santé" });

    lineChart(document.getElementById("chart-trend"), DATES.map((d) => {
      const r = atDate(P.summary, d).find((x) => x.province === prov);
      return { date: d, value: r ? r.cumul_confirmes : null, extra: r ? [["Décès", fmt(r.cumul_deces)]] : [] };
    }), { label: "Confirmés (cumul)", empty: "Cumul non extrait.", aria: `Cumul des cas confirmés, ${prov}` });

    renderTable(document.getElementById("table-zones"), [
      { key: "zone", label: "Zone de santé", render: (r) => esc(r.zone) + (r.zone_resolved === false ? ' <span title="Nom non reconnu dans le référentiel des ZS">⚠</span>' : "") },
      { key: "cumul_confirmes", label: "Confirmés", num: true, fmt },
      { key: "cumul_deces", label: "Décès", num: true, fmt },
      { key: "letalite", label: "Létalité", num: true, fmt: fmtPct },
      { key: "confirmes_21j", label: "Confirmés 21 j", num: true, fmt },
      { key: "deces_21j", label: "Décès 21 j", num: true, fmt },
      { key: "date_dernier_cas", label: "Dernier cas", render: (r) => (r.date_dernier_cas ? esc(frDate(r.date_dernier_cas)) : '<span class="na">–</span>') },
      { key: "jours_depuis_dernier_cas", label: "Jours depuis", num: true, fmt },
      { key: "statut", label: "Statut", sortValue: (r) => r.jours_depuis_dernier_cas, render: zoneStatus },
    ], cases, { sortKey: "cumul_confirmes", empty: "Aucun tableau des cas extrait pour cette date." });

    bulletChart(document.getElementById("chart-contacts"),
      contacts.filter((r) => (r.a_suivre || 0) > 0).sort((a, b) => b.a_suivre - a.a_suivre).map((r) => ({ label: r.zone, total: r.a_suivre, part: r.vus })),
      { totalLabel: "À suivre", partLabel: "Vus", empty: "Aucun tableau de contacts extrait.", aria: "Contacts à suivre et vus" });

    const parts = Object.fromEntries(sources.map((r) => [r.source, r.total || 0]));
    stackedChart(document.getElementById("chart-sources"), sources.length ? [{ label: prov, parts }] : [], SOURCE_ORDER, SOURCE_LABELS, { empty: "Aucun tableau des sources extrait.", aria: "Sources des alertes" });
    renderTable(document.getElementById("table-sources"), [
      { key: "source", label: "Source", render: (r) => esc(SOURCE_LABELS[r.source] || r.source) },
      { key: "vivants", label: "Vivants", num: true, fmt },
      { key: "deces", label: "Décès", num: true, fmt },
      { key: "total", label: "Total", num: true, fmt },
    ], sources, { sortKey: "total" });

    const alertRows = zoneAlerts.length
      ? zoneAlerts.map((r) => ({ ...r, lieu: r.zone, niveau: "ZS" }))
      : aireAlerts.map((r) => ({ ...r, lieu: r.aire_sante + (r.zone ? ` (${r.zone})` : ""), niveau: "AS" }));
    const nouvelles = (r) => (isNum(r.nouvelles_alertes_vivants) || isNum(r.nouvelles_alertes_deces) ? (r.nouvelles_alertes_vivants || 0) + (r.nouvelles_alertes_deces || 0) : null);
    const validees = (r) => (isNum(r.validees_vivants) || isNum(r.validees_deces) ? (r.validees_vivants || 0) + (r.validees_deces || 0) : null);
    renderTable(document.getElementById("table-alerts"), [
      { key: "lieu", label: zoneAlerts.length ? "Zone de santé" : "Aire de santé (ZS)" },
      { key: "nouvelles", label: "Nouvelles", num: true, sortValue: nouvelles, render: (r) => fmt(nouvelles(r)) },
      { key: "nouvelles_alertes_deces", label: "dont décès", num: true, fmt },
      { key: "total_alertes", label: "Total alertes", num: true, fmt },
      { key: "validees", label: "Validées", num: true, sortValue: validees, render: (r) => fmt(validees(r)) },
      { key: "invalidees_vivants", label: "Invalidées", num: true, fmt },
    ], alertRows.filter((r) => isNum(r.total_alertes) || isNum(nouvelles(r))), { sortKey: "total_alertes", empty: cov && cov.image.alerts ? "Tableau des alertes collé en image : non extrait." : "Aucun tableau d'alertes extrait pour cette date." });

    renderTable(document.getElementById("table-contacts"), [
      { key: "zone", label: "Zone de santé" },
      { key: "a_suivre", label: "À suivre", num: true, fmt },
      { key: "vus", label: "Vus", num: true, fmt },
      { key: "taux", label: "Taux de suivi", num: true, sortValue: (r) => pct(r.vus, r.a_suivre), render: (r) => fmtPct(pct(r.vus, r.a_suivre) ?? r.taux_suivi_pct) },
      { key: "nouveaux", label: "Nouveaux", num: true, fmt },
      { key: "devenus_suspects", label: "Devenus suspects", num: true, fmt },
      { key: "perdus_de_vue", label: "Perdus de vue", num: true, fmt },
      { key: "jamais_vus", label: "Jamais vus", num: true, fmt },
    ], contacts.filter((r) => (r.a_suivre || 0) > 0 || (r.vus || 0) > 0), { sortKey: "a_suivre", empty: "Aucun tableau de contacts extrait pour cette date." });

    const covEl = document.getElementById("prov-coverage");
    covEl.innerHTML = cov ? ["cases", "alerts", "contacts", "alert_sources"].map((k) => {
      if (cov.ok.includes(k)) return pill("good", "✓", `${TABLE_LABELS[k]} : extrait`);
      if (k === "alert_sources") return pill("neutral", "–", "sources : non trouvé");
      return cov.image[k] ? pill("warn", "!", `${TABLE_LABELS[k]} : image`) : pill("crit", "✕", `${TABLE_LABELS[k]} : absent`);
    }).join(" ") : pill("neutral", "–", "présentation non reçue");
    renderTable(document.getElementById("table-qa"), [
      { key: "status", label: "Niveau", render: (q) => (q.status === "fail" ? pill("crit", "✕", "Bloquant") : pill("warn", "!", "Avertissement")) },
      { key: "check", label: "Contrôle", render: (q) => esc(CHECK_LABELS[q.check] || q.check) },
      { key: "detail", label: "Détail", cls: "detail", sortable: false },
    ], qa, { sortKey: "status", desc: false, empty: "Aucun constat de la QA pour cette date." });
    renderProvinceKpis(prov);
    renderProvincePillars(prov);
  }

  // ════════════════════════════════════════════════════════════
  // Extraction des présentations : coordination, piliers, fiabilité
  // (P.extraction, produit par extraire_rapports.py — 3 méthodes de lecture du texte comparées)
  // ════════════════════════════════════════════════════════════
  const EXT = P.extraction || [];
  const EXT_LABELS = P.extraction_labels || { piliers: {}, sections: {} };
  const SECTION_NAMES = { points_saillants: "Points saillants", realisations: "Réalisations", defis: "Défis et décisions", planification: "Planification", recommandations: "Recommandations" };
  const extDates = () => [...new Set(EXT.map((r) => r.date))].sort();
  const extAt = (d) => EXT.filter((r) => r.date === d);
  function extDateFor(d) {
    const ds = extDates();
    if (!ds.length) return null;
    if (ds.includes(d)) return d;
    const before = ds.filter((x) => x <= d);
    return before.length ? before[before.length - 1] : ds[ds.length - 1];
  }
  const fiabPill = (f) => (!f || !isNum(f.score)
    ? pill("neutral", "–", "non évaluée")
    : pill(f.score >= 85 ? "good" : f.score >= 65 ? "warn" : "crit", f.score >= 85 ? "✓" : "!", `${f.score}/100 · ${f.niveau}`));
  const confBadge = (c, n) => (c == null ? "" : `<span class="conf ${c >= Math.min(2, n) ? "ok" : "low"}" title="Retrouvé par ${c} méthode(s) de lecture sur ${n}">${c}/${n}</span>`);
  const cle = (r, k) => (r.cles || {})[k];
  const cleNum = (r, k) => { const c = cle(r, k); return c && isNum(c.n) ? c.n : null; };
  const cleCell = (r, k, frac) => {
    const c = cle(r, k);
    if (!c || !isNum(c.n)) return '<span class="na">–</span>';
    const txt = frac && isNum(c.d) ? `${fmt(c.n)}/${fmt(c.d)}` : fmt(c.n);
    return `<span class="src-tip" title="${esc(`${c.l} : « ${c.v} » · diapositive ${c.s} (${c.src === "tableau" ? "ligne Total du tableau par ZS" : c.src})`)}">${txt}</span>`;
  };
  const OCR_TAG = '<span class="ocr-tag" title="Lu par OCR sur une diapositive en image : à vérifier dans le PowerPoint">OCR</span>';
  const ctrlPill = (n) => (n === "erreur" ? pill("crit", "✕", "Erreur") : n === "attention" ? pill("warn", "!", "À vérifier") : pill("neutral", "i", "Info"));
  const pillarOrder = () => Object.keys(EXT_LABELS.piliers || {});
  function extNote(el, d) {
    if (!el) return;
    let msg = "";
    if (!d) msg = "Aucune extraction des présentations : lancer <code>extraire_rapports.py</code> dans <code>BDBV2026-Provincial_Reports/data/presentations</code>, puis reconstruire le dashboard.";
    else if (d !== DATE) msg = `Pas d'extraction des présentations pour le ${esc(frDate(DATE))} : affichage du ${esc(frDate(d))}, la date disponible la plus proche.`;
    el.innerHTML = msg;
    el.classList.toggle("show", !!msg);
  }

  function renderPillars() {
    const d = extDateFor(DATE);
    extNote(document.getElementById("extraction-note"), d);
    const rows = d ? extAt(d) : [];
    const sumKey = (k) => { let s = 0, n = 0; rows.forEach((r) => { const v = cleNum(r, k); if (isNum(v)) { s += v; n++; } }); return { s: n ? s : null, n }; };
    const nP = rows.length;
    const cj = sumKey("cas_jour"), cc = sumKey("cumul_confirmes"), cd = sumKey("cumul_deces"), al = sumKey("alertes");
    // létalité sur les seules provinces qui donnent à la fois le cumul et les décès
    const both = rows.filter((r) => isNum(cleNum(r, "cumul_confirmes")) && isNum(cleNum(r, "cumul_deces")));
    const letal = pct(both.reduce((a, r) => a + cleNum(r, "cumul_deces"), 0), both.reduce((a, r) => a + cleNum(r, "cumul_confirmes"), 0));
    const scores = rows.map((r) => (r.fiabilite || {}).score).filter(isNum);
    const nErr = rows.reduce((a, r) => a + (r.controles || []).filter((c) => c.niveau === "erreur").length, 0);
    const nAtt = rows.reduce((a, r) => a + (r.controles || []).filter((c) => c.niveau === "attention").length, 0);
    const kpis = [
      { label: "Cas confirmés du jour", value: fmt(cj.s), sub: `${cj.n}/${nP} provinces le rapportent` },
      { label: "Cumul des confirmés", value: fmt(cc.s), sub: `${cc.n}/${nP} provinces` },
      { label: "Cumul des décès", value: fmt(cd.s), sub: `${cd.n}/${nP} provinces · létalité ${fmtPct(letal)} (${both.length} prov.)` },
      { label: "Alertes du jour", value: fmt(al.s), sub: `${al.n}/${nP} provinces` },
      { label: "Fiabilité moyenne", value: scores.length ? `${Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)}/100` : "–", sub: scores.length ? `min. ${Math.min(...scores)}/100 · ${nP} présentations` : "" },
      { label: "Contrôles à vérifier", value: fmt(nErr + nAtt), sub: `${fmt(nErr)} erreur(s) · ${fmt(nAtt)} point(s) d'attention` },
    ];
    document.getElementById("kpis").innerHTML = kpis.map((k) =>
      `<div class="kpi"><div class="label">${esc(k.label)}</div><div class="value">${k.value}</div><div class="sub">${esc(k.sub)}</div></div>`).join("");

    const num = (k) => ({ key: k, num: true, sortValue: (r) => cleNum(r, k), render: (r) => cleCell(r, k) });
    renderTable(document.getElementById("table-cles"), [
      { key: "province", label: "Province", render: (r) => provLink(r.province) },
      { key: "fiab", label: "Fiabilité", sortValue: (r) => (r.fiabilite || {}).score, render: (r) => fiabPill(r.fiabilite) },
      { ...num("cas_jour"), label: "Cas du jour" },
      { ...num("cumul_confirmes"), label: "Cumul confirmés" },
      { ...num("cumul_deces"), label: "Cumul décès" },
      { key: "let", label: "Létalité", num: true, sortValue: (r) => pct(cleNum(r, "cumul_deces"), cleNum(r, "cumul_confirmes")), render: (r) => fmtPct(pct(cleNum(r, "cumul_deces"), cleNum(r, "cumul_confirmes"))) },
      { key: "zs", label: "ZS touchées", sortable: false, render: (r) => cleCell(r, "zs_touchees", true) },
      { key: "as", label: "AS touchées", sortable: false, render: (r) => cleCell(r, "as_touchees", true) },
      { ...num("alertes"), label: "Alertes du jour" },
      { ...num("gueris"), label: "Guéris (cumul)" },
      { ...num("patients_lits"), label: "Patients aux lits" },
    ], rows, { sortKey: "cumul_confirmes", empty: "Aucune présentation extraite pour cette date." });

    hbarChart(document.getElementById("chart-fiabilite"), rows.slice().sort((a, b) => ((b.fiabilite || {}).score ?? -1) - ((a.fiabilite || {}).score ?? -1)).map((r) => {
      const f = r.fiabilite || {};
      return { label: r.province, value: f.score, tip: [["Score", `${f.score}/100 (${f.niveau})`], ["Éléments confirmés", fmtPct(f.elements_confirmes_pct)], ["Accord du texte", fmtPct(f.accord_texte_pct)], ["Vu à l'écran (OCR)", isNum(f.confirmation_ocr_pct) ? fmtPct(f.confirmation_ocr_pct) : "sans OCR"], ["Couverture", fmtPct(f.couverture_pct)], ["Cohérence", fmtPct(f.coherence_pct)]] };
    }), { max: 100, format: (v) => `${fmt(v)}/100`, empty: "Aucune extraction.", aria: "Fiabilité de l'extraction par province" });

    const ctrls = rows.flatMap((r) => (r.controles || []).map((c) => ({ ...c, province: r.province })));
    renderTable(document.getElementById("table-controles"), [
      { key: "province", label: "Province", render: (c) => provLink(c.province) },
      { key: "niveau", label: "Niveau", sortValue: (c) => ({ erreur: 0, attention: 1 }[c.niveau] ?? 2), render: (c) => ctrlPill(c.niveau) },
      { key: "detail", label: "Constat", cls: "detail", sortable: false },
      { key: "diapositive", label: "Diapo", num: true, fmt },
    ], ctrls, { sortKey: "niveau", desc: false, empty: "Aucune incohérence détectée." });

    renderTable(document.getElementById("table-fiabilite"), [
      { key: "province", label: "Province", render: (r) => provLink(r.province) },
      { key: "score", label: "Score", num: true, sortValue: (r) => (r.fiabilite || {}).score, render: (r) => fiabPill(r.fiabilite) },
      { key: "el", label: "Éléments confirmés", num: true, sortValue: (r) => (r.fiabilite || {}).elements_confirmes_pct, render: (r) => fmtPct((r.fiabilite || {}).elements_confirmes_pct) },
      { key: "ac", label: "Accord du texte", num: true, sortValue: (r) => (r.fiabilite || {}).accord_texte_pct, render: (r) => fmtPct((r.fiabilite || {}).accord_texte_pct) },
      { key: "oc", label: "Vu à l'écran (OCR)", num: true, sortValue: (r) => (r.fiabilite || {}).confirmation_ocr_pct, render: (r) => fmtPct((r.fiabilite || {}).confirmation_ocr_pct) },
      { key: "co", label: "Couverture", num: true, sortValue: (r) => (r.fiabilite || {}).couverture_pct, render: (r) => fmtPct((r.fiabilite || {}).couverture_pct) },
      { key: "ch", label: "Cohérence", num: true, sortValue: (r) => (r.fiabilite || {}).coherence_pct, render: (r) => fmtPct((r.fiabilite || {}).coherence_pct) },
      { key: "me", label: "Méthodes", sortable: false, render: (r) => esc(((r.fiabilite || {}).methodes || []).join(" · ")) },
      { key: "img", label: "Diapos en image", sortable: false, render: (r) => { const f = r.fiabilite || {}, o = f.diapositives_lues_ocr || []; return esc((f.diapositives_image || []).join(", ") || "–") + (o.length ? ` <span class="muted">(lues par OCR : ${esc(o.join(", "))})</span>` : ""); } },
      { key: "inc", label: "Piliers incertains", sortable: false, render: (r) => esc(((r.fiabilite || {}).piliers_incertains || []).join(", ") || "–") },
    ], rows, { sortKey: "score", empty: "Aucune extraction." });

    const pSel = document.getElementById("pillar-select"), sSel = document.getElementById("section-select");
    if (!pSel.dataset.bound) {
      pSel.dataset.bound = "1";
      pSel.innerHTML = `<option value="">Tous</option>` + pillarOrder().map((k) => `<option value="${esc(k)}">${esc(EXT_LABELS.piliers[k])}</option>`).join("");
      sSel.innerHTML = Object.entries(SECTION_NAMES).map(([k, v]) => `<option value="${k}"${k === "points_saillants" ? " selected" : ""}>${esc(v)}</option>`).join("");
      pSel.addEventListener("change", renderPillars);
      sSel.addEventListener("change", renderPillars);
    }
    const pv = pSel.value, sv = sSel.value;
    const blocs = pillarOrder().filter((k) => !pv || k === pv).map((k) => {
      const items = rows.flatMap((r) => (r.piliers || []).filter((pl) => pl.id === k)
        .flatMap((pl) => (pl.sections[sv] || []).map((it) => ({ ...it, province: r.province, n: r.n_methodes }))));
      if (!items.length) return "";
      return `<section class="pillar-block"><h4>${esc(EXT_LABELS.piliers[k])} <span class="count">${items.length}</span></h4><ul>`
        + items.map((it) => `<li><span class="prov-tag">${esc(it.province)}</span> ${esc(it.t)} <span class="ref" title="Diapositive">diapo ${it.s}</span> ${it.o ? OCR_TAG : confBadge(it.c, it.n)}</li>`).join("")
        + "</ul></section>";
    }).join("");
    document.getElementById("pillar-items").innerHTML = blocs || `<p class="empty">Aucun élément « ${esc(SECTION_NAMES[sv])} » pour cette sélection.</p>`;
  }

  function renderProvincePillars(prov) {
    const root = document.getElementById("prov-pillars");
    if (!root) return;
    const d = extDateFor(DATE);
    const r = d ? extAt(d).find((x) => x.province === prov) : null;
    const fEl = document.getElementById("prov-fiabilite"), cEl = document.getElementById("prov-controles");
    if (!r) {
      fEl.innerHTML = "";
      cEl.innerHTML = "";
      root.innerHTML = `<p class="empty">Aucune extraction de la présentation de cette province${d ? ` au ${esc(frDate(d))}` : ""}.</p>`;
      return;
    }
    const f = r.fiabilite || {};
    fEl.innerHTML = `Fiabilité de l'extraction : ${fiabPill(f)}${d !== DATE ? ` <em>(présentation du ${esc(frDate(d))})</em>` : ""}`
      + (() => {
        const img = f.diapositives_image || [], o = f.diapositives_lues_ocr || [], nl = img.filter((x) => !o.includes(x));
        return (o.length ? ` · diapositives en image lues par OCR : ${esc(o.join(", "))}` : "") + (nl.length ? ` · non lues : ${esc(nl.join(", "))}` : "");
      })();
    cEl.innerHTML = (r.controles || []).length
      ? `<ul class="ctrl-list">${r.controles.map((c) => `<li>${ctrlPill(c.niveau)} ${esc(c.detail)}${c.diapositive ? ` <span class="ref">diapo ${c.diapositive}</span>` : ""}</li>`).join("")}</ul>`
      : "";
    const order = pillarOrder();
    const pls = (r.piliers || []).slice().sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
    root.innerHTML = pls.map((pl, i) => {
      const cards = pl.indicateurs.length
        ? `<div class="ext-cards">${pl.indicateurs.map((x) => `<div class="ext-card"><div class="lab">${esc(x.l)}</div><div class="val">${esc(x.v)}</div>${x.det ? `<div class="det">${esc(x.det)}</div>` : ""}<div class="meta">diapo ${x.s} ${confBadge(x.c, r.n_methodes)}</div></div>`).join("")}</div>`
        : "";
      const secs = Object.keys(SECTION_NAMES).filter((k) => (pl.sections[k] || []).length).map((k) =>
        `<h5 class="sec-${k}">${esc(SECTION_NAMES[k])}</h5><ul>${pl.sections[k].map((it) => `<li>${esc(it.t)} <span class="ref">diapo ${it.s}</span> ${it.o ? OCR_TAG : confBadge(it.c, r.n_methodes)}</li>`).join("")}</ul>`).join("");
      const inc = pl.incertain.length ? ` <span class="pill warn" title="Pilier déduit du contexte avec une confiance faible"><span class="dot"></span>à vérifier : diapo ${esc(pl.incertain.join(", "))}</span>` : "";
      return `<details class="pillar"${i < 2 ? " open" : ""}><summary><strong>${esc(pl.libelle)}</strong> <span class="muted">diapositives ${esc(pl.diapos.join(", "))}</span>${inc}</summary>${cards}${secs || (cards ? "" : '<p class="empty">Contenu sous forme de tableaux ou d\'images : voir le rapport d\'extraction du jour.</p>')}</details>`;
    }).join("") || '<p class="empty">Aucun pilier extrait.</p>';
  }


  // ════════════════════════════════════════════════════════════
  // KPI Surveillance · Labo · PCI (r.kpi, calculés par kpi_piliers.py)
  // ════════════════════════════════════════════════════════════
  const KPI_PILIERS = ["surveillance", "laboratoire", "pci"];
  const KPI_NOMS = { surveillance: "Surveillance", laboratoire: "Laboratoire", pci: "PCI / WASH" };
  const KPI_SRC = { tableau: "ligne Total d'un tableau", evolution: "tableau ou graphique d'évolution (colonne du jour)", carte: "carte d'indicateur", texte: "phrase", ocr: "OCR d'une diapositive en image", calcul: "calculé" };
  const kpiDefs = (pil) => ((EXT_LABELS.kpi || {})[pil] || []);
  const kpiOf = (r, pil, k) => ((r.kpi || {})[pil] || {})[k];
  const isRate = (pil, k) => /^taux_|^part_|^completude$/.test(k);
  // tuiles retenues pour la synthèse (les autres KPI restent dans le tableau)
  const KPI_TUILES = {
    surveillance: ["alertes_total", "taux_verification", "alertes_validees", "taux_transfert", "part_recherche_active", "completude"],
    laboratoire: ["echantillons_recus", "echantillons_testes", "echantillons_en_cours", "positifs", "taux_positivite"],
    pci: ["rings", "ess_decont", "menages_decont", "menages_dotes", "ppl_infectes"],
  };
  function kpiAgg(rows, pil, k) {
    const vals = rows.map((r) => kpiOf(r, pil, k)).filter((v) => v && isNum(v.n));
    if (!vals.length) return null;
    const avecD = vals.filter((v) => isNum(v.d));
    const n = vals.reduce((a, v) => a + v.n, 0);
    const nd = avecD.reduce((a, v) => a + v.n, 0), d = avecD.reduce((a, v) => a + v.d, 0);
    return { n, nd, d: avecD.length ? d : null, p: avecD.length ? pct(nd, d) : null, nProv: vals.length, nProvD: avecD.length };
  }
  function kpiCell(r, pil, k) {
    const v = kpiOf(r, pil, k);
    if (!v || !isNum(v.n)) return '<span class="na">–</span>';
    const nm = (r.methodes || []).length || r.n_methodes || 0;
    const main = isRate(pil, k) && isNum(v.p) ? fmtPct(v.p) : isNum(v.d) ? `${fmt(v.n)}/${fmt(v.d)}` : fmt(v.n);
    const sub = isRate(pil, k) && isNum(v.d) ? `<span class="kpi-frac">${fmt(v.n)}/${fmt(v.d)}</span>` : (!isRate(pil, k) && isNum(v.p) ? `<span class="kpi-frac">${fmtPct(v.p)}</span>` : "");
    const tip = `${v.l || ""} · diapositive ${v.s} · ${KPI_SRC[v.src] || v.src}${v.src !== "calcul" && v.c != null ? ` · retrouvé par ${v.c}/${nm} méthodes` : ""}`;
    const ocr = v.src === "ocr" ? ' <span class="ocr-tag" title="Lu par OCR">OCR</span>' : "";
    return `<span class="src-tip" title="${esc(tip)}">${main}</span>${sub}${ocr}${v.src !== "calcul" ? " " + confBadge(v.c, nm) : ""}`;
  }
  function kpiTiles(el, rows, pil) {
    if (!el) return;
    const defs = Object.fromEntries(kpiDefs(pil).map((x) => [x.cle, x.libelle]));
    const nP = rows.length;
    el.innerHTML = (KPI_TUILES[pil] || []).filter((k) => defs[k]).map((k) => {
      const a = kpiAgg(rows, pil, k);
      let value = "–", sub = `0/${nP} provinces`;
      if (a) {
        if (isRate(pil, k)) { value = fmtPct(a.p); sub = `${fmt(a.nd)}/${fmt(a.d)} · ${a.nProvD}/${nP} provinces`; }
        else if (a.d != null && a.nProvD === a.nProv) { value = fmt(a.n); sub = `sur ${fmt(a.d)} (${fmtPct(a.p)}) · ${a.nProv}/${nP} provinces`; }
        else { value = fmt(a.n); sub = `${a.nProv}/${nP} provinces`; }
      }
      return `<div class="kpi"><div class="label">${esc(defs[k])}</div><div class="value">${value}</div><div class="sub">${esc(sub)}</div></div>`;
    }).join("");
  }
  function kpiTable(el, rows, pil) {
    const defs = kpiDefs(pil);
    const present = defs.filter((x) => rows.some((r) => kpiOf(r, pil, x.cle)));
    renderTable(el, [
      { key: "province", label: "Province", render: (r) => provLink(r.province) },
      ...present.map((x) => ({ key: x.cle, label: x.libelle, num: true,
        sortValue: (r) => { const v = kpiOf(r, pil, x.cle); return v ? (isRate(pil, x.cle) ? v.p : v.n) : null; },
        render: (r) => kpiCell(r, pil, x.cle) })),
    ], rows.filter((r) => Object.keys((r.kpi || {})[pil] || {}).length), { sortKey: present.length ? present[0].cle : null,
      empty: `Aucun KPI ${KPI_NOMS[pil]} extrait pour cette date.` });
  }
  function kpiChart(el, rows, pil) {
    if (pil === "surveillance") {
      const items = rows.filter((r) => kpiOf(r, pil, "alertes_total")).map((r) => ({
        label: r.province, total: kpiOf(r, pil, "alertes_total").n, part: (kpiOf(r, pil, "alertes_verifiees") || {}).n }))
        .sort((a, b) => b.total - a.total);
      bulletChart(el, items, { totalLabel: "Alertes du jour", partLabel: "Vérifiées / investiguées", empty: "Aucune alerte extraite.", aria: "Alertes vérifiées sur alertes du jour, par province" });
    } else if (pil === "laboratoire") {
      const items = rows.filter((r) => kpiOf(r, pil, "taux_positivite")).map((r) => {
        const v = kpiOf(r, pil, "taux_positivite");
        return { label: r.province, value: v.p, tip: [["Positifs", fmt(v.n)], ["Analysés", fmt(v.d)], ["Taux de positivité", fmtPct(v.p)]] };
      }).sort((a, b) => b.value - a.value);
      hbarChart(el, items, { format: fmtPct, max: Math.max(10, ...items.map((i) => i.value || 0)) * 1.15, empty: "Aucun taux de positivité calculable (positifs et analysés).", aria: "Taux de positivité par province", color: "--series-2" });
    } else {
      const keys = [["rings", "Rings ouverts"], ["ess_decont", "ESS / FOSA décont."], ["menages_decont", "Ménages décont."]];
      const items = [];
      rows.forEach((r) => keys.forEach(([k, lab]) => {
        const v = kpiOf(r, pil, k);
        if (v && isNum(v.p)) items.push({ label: `${r.province} · ${lab}`, value: v.p, tip: [[lab, `${fmt(v.n)}/${fmt(v.d)}`], ["Couverture", fmtPct(v.p)], ["Diapositive", String(v.s)]] });
      }));
      hbarChart(el, items, { format: fmtPct, max: 100, empty: "Aucun taux PCI calculable (numérateur et dénominateur).", aria: "Taux de couverture PCI", color: "--series-3" });
    }
  }
  function renderKpis() {
    const d = extDateFor(DATE);
    extNote(document.getElementById("extraction-note"), d);
    const rows = d ? extAt(d) : [];
    KPI_PILIERS.forEach((pil) => {
      kpiTiles(document.getElementById(`kpis-${pil}`), rows, pil);
      kpiChart(document.getElementById(`chart-${pil}`), rows, pil);
      kpiTable(document.getElementById(`table-${pil}`), rows, pil);
    });
  }
  function renderProvinceKpis(prov) {
    const root = document.getElementById("prov-kpis");
    if (!root) return;
    const d = extDateFor(DATE);
    const r = d ? extAt(d).find((x) => x.province === prov) : null;
    if (!r || !KPI_PILIERS.some((p) => Object.keys((r.kpi || {})[p] || {}).length)) {
      root.innerHTML = `<p class="empty">Aucun KPI Surveillance, Labo ou PCI extrait de la présentation de cette province${d ? ` au ${esc(frDate(d))}` : ""}.</p>`;
      return;
    }
    root.innerHTML = KPI_PILIERS.map((pil) => {
      const defs = kpiDefs(pil).filter((x) => kpiOf(r, pil, x.cle));
      const corps = defs.length
        ? `<dl>${defs.map((x) => `<div class="kv"><dt>${esc(x.libelle)}</dt><dd>${kpiCell(r, pil, x.cle)}</dd></div>`).join("")}</dl>`
        : '<p class="empty">Non présenté ou non extrait.</p>';
      return `<section class="kpi-group"><h4>${esc(KPI_NOMS[pil])}</h4>${corps}</section>`;
    }).join("") + (d !== DATE ? `<p class="muted small">Présentation du ${esc(frDate(d))}.</p>` : "");
  }


  // ════════════════════════════════════════════════════════════
  // Résumé de la semaine : une fenêtre par pilier (lundi → dimanche contenant la date choisie)
  // ════════════════════════════════════════════════════════════
  const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];
  const isoDay = (iso) => new Date(iso + "T00:00:00Z").getUTCDay();
  const addDays = (iso, n) => new Date(Date.parse(iso + "T00:00:00Z") + n * 864e5).toISOString().slice(0, 10);
  const weekStart = (iso) => addDays(iso, -((isoDay(iso) + 6) % 7));
  const jourCourt = (iso) => `${JOURS[isoDay(iso)]} ${shortDate(iso)}`;
  // flux : on additionne sur la semaine ; les autres KPI gardent la dernière valeur de la semaine
  const KPI_FLUX = new Set(["alertes_total", "alertes_nouvelles", "alertes_verifiees", "alertes_validees", "suspects_transferes",
    "echantillons_recus", "echantillons_testes", "positifs"]);
  const CLES_SEMAINE = [["cas_jour", "Cas confirmés du jour", "flux"], ["alertes", "Alertes du jour", "flux"],
    ["cumul_confirmes", "Cumul des confirmés", "stock"], ["cumul_deces", "Cumul des décès", "stock"],
    ["gueris", "Cumul des guéris", "stock"], ["patients_lits", "Patients aux lits", "stock"]];
  const motsCles = (t) => new Set(normKey(t).split(" ").filter((w) => w.length >= 3 && !/\d/.test(w)));
  const jaccard = (a, b) => { let i = 0; a.forEach((w) => { if (b.has(w)) i++; }); const u = a.size + b.size - i; return u ? i / u : 0; };

  /** Regroupe les éléments répétés d'un jour à l'autre (même province, même rubrique, mots presque identiques). */
  function regrouper(items) {
    const groupes = [];
    items.forEach((it) => {
      const m = motsCles(it.t);
      const g = groupes.find((x) => x.province === it.province && (m.size ? jaccard(m, x.mots) >= 0.7 : x.t === it.t));
      if (g) {
        if (!g.dates.includes(it.date)) g.dates.push(it.date);
        if (it.date >= g.date) { g.t = it.t; g.date = it.date; g.s = it.s; g.o = it.o; }
        m.forEach((w) => g.mots.add(w));
      } else groupes.push({ ...it, mots: m, dates: [it.date] });
    });
    return groupes;
  }

  function weekKpiTable(rowsSem, jours, pil) {
    const defs = pil === "coordination" ? CLES_SEMAINE.map(([cle, libelle, type]) => ({ cle, libelle, type }))
      : kpiDefs(pil).map((x) => ({ ...x, type: isRate(pil, x.cle) ? "taux" : KPI_FLUX.has(x.cle) ? "flux" : "stock" }));
    const get = (r, cle) => (pil === "coordination" ? (r.cles || {})[cle] : kpiOf(r, pil, cle));
    const lignes = defs.map((x) => {
      const parJour = jours.map((j) => {
        const vs = rowsSem.filter((r) => r.date === j).map((r) => get(r, x.cle)).filter((v) => v && isNum(v.n));
        if (!vs.length) return null;
        const n = vs.reduce((a, v) => a + v.n, 0);
        const avecD = vs.filter((v) => isNum(v.d));
        return { n, nd: avecD.reduce((a, v) => a + v.n, 0), d: avecD.length ? avecD.reduce((a, v) => a + v.d, 0) : null, k: vs.length };
      });
      if (!parJour.some(Boolean)) return null;
      const presents = parJour.filter(Boolean);
      let sem;
      if (x.type === "flux") sem = { n: presents.reduce((a, v) => a + v.n, 0) };
      else if (x.type === "taux") { const nd = presents.reduce((a, v) => a + (v.d != null ? v.nd : 0), 0), d = presents.reduce((a, v) => a + (v.d || 0), 0); sem = { n: nd, d, p: pct(nd, d) }; }
      else { const der = presents[presents.length - 1], pre = presents[0]; sem = { ...der, delta: presents.length > 1 && x.type === "stock" ? der.n - pre.n : null }; }
      return { x, parJour, sem };
    }).filter(Boolean);
    if (!lignes.length) return "";
    const cell = (x, v) => {
      if (!v) return '<td class="num"><span class="na">–</span></td>';
      if (x.type === "taux") return `<td class="num">${isNum(v.d) && v.d > 0 ? fmtPct(pct(v.nd ?? v.n, v.d)) : "–"}<span class="kpi-frac">${isNum(v.d) ? `${fmt(v.nd ?? v.n)}/${fmt(v.d)}` : ""}</span></td>`;
      return `<td class="num">${fmt(v.n)}${isNum(v.d) ? `<span class="kpi-frac">/${fmt(v.d)}</span>` : ""}</td>`;
    };
    const semCell = (x, v) => {
      if (x.type === "taux") return `<td class="num week-col">${fmtPct(v.p)}<span class="kpi-frac">${fmt(v.n)}/${fmt(v.d)}</span></td>`;
      if (x.type === "flux") return `<td class="num week-col">${fmt(v.n)}<span class="kpi-frac">total</span></td>`;
      const dl = isNum(v.delta) && v.delta !== 0 ? `<span class="kpi-frac">${v.delta > 0 ? "+" : ""}${fmt(v.delta)} sur la semaine</span>` : `<span class="kpi-frac">dernier jour</span>`;
      return `<td class="num week-col">${fmt(v.n)}${isNum(v.d) ? `<span class="kpi-frac">/${fmt(v.d)}</span>` : ""}${dl}</td>`;
    };
    return `<div class="table-wrap"><table class="week-kpi"><thead><tr><th scope="col">Indicateur</th>${jours.map((j) => `<th scope="col" class="num">${esc(jourCourt(j))}</th>`).join("")}<th scope="col" class="num week-col">Semaine</th></tr></thead><tbody>`
      + lignes.map(({ x, parJour, sem }) => `<tr><th scope="row">${esc(x.libelle)}</th>${parJour.map((v) => cell(x, v)).join("")}${semCell(x, sem)}</tr>`).join("")
      + "</tbody></table></div>";
  }

  function renderWeek() {
    const ds = extDates();
    const ref = extDateFor(DATE);
    extNote(document.getElementById("extraction-note"), ref);
    const root = document.getElementById("week-pillars");
    if (!ref) { root.innerHTML = ""; return; }
    const lundi = weekStart(ref), dimanche = addDays(lundi, 6);
    const jours = ds.filter((d) => d >= lundi && d <= dimanche);
    const pSel = document.getElementById("week-province"), sSel = document.getElementById("week-section"), plSel = document.getElementById("week-pillar");
    const tog = document.getElementById("week-toggle");
    if (!pSel.dataset.bound) {
      pSel.dataset.bound = "1";
      const provs = [...new Set(EXT.map((r) => r.province))].sort((a, b) => a.localeCompare(b, "fr"));
      pSel.innerHTML = `<option value="">Toutes</option>` + provs.map((p) => `<option>${esc(p)}</option>`).join("");
      sSel.innerHTML = `<option value="">Toutes</option>` + Object.entries(SECTION_NAMES).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
      plSel.innerHTML = `<option value="">Tous</option>` + pillarOrder().map((k) => `<option value="${esc(k)}">${esc(EXT_LABELS.piliers[k])}</option>`).join("");
      [pSel, sSel, plSel].forEach((el) => el.addEventListener("change", renderWeek));
      tog.addEventListener("click", () => {
        const ouvrir = tog.getAttribute("aria-pressed") !== "true";
        tog.setAttribute("aria-pressed", String(ouvrir));
        tog.textContent = ouvrir ? "Tout replier" : "Tout déplier";
        root.querySelectorAll("details.week-pillar").forEach((d) => { d.open = ouvrir; });
      });
    }
    const prov = pSel.value, secF = sSel.value, pilF = plSel.value;
    const rowsSem = EXT.filter((r) => jours.includes(r.date) && (!prov || r.province === prov));
    const provsSem = [...new Set(rowsSem.map((r) => r.province))];
    document.getElementById("week-intro").innerHTML =
      `Semaine du <strong>${esc(frDate(lundi))}</strong> au <strong>${esc(frDate(dimanche))}</strong> : `
      + `${jours.length} jour(s) de présentations (${esc(jours.map(jourCourt).join(", ") || "aucun")}), ${rowsSem.length} présentation(s), `
      + `${provsSem.length} province(s). Un point repris plusieurs jours n'apparaît qu'une fois, avec le nombre de jours où il revient ; `
      + `un défi présent tous les jours est signalé comme <em>persistant</em>.`;

    // ── la semaine en chiffres
    const somme = (f) => rowsSem.reduce((a, r) => { const v = f(r); return isNum(v) ? a + v : a; }, 0);
    const nAvec = (f) => rowsSem.filter((r) => isNum(f(r))).length;
    const casSem = somme((r) => cleNum(r, "cas_jour"));
    const alertesSem = somme((r) => (kpiOf(r, "surveillance", "alertes_total") || {}).n ?? cleNum(r, "alertes"));
    const posSem = somme((r) => { const p = kpiOf(r, "laboratoire", "taux_positivite"); return p ? p.n : null; });
    const testSem = somme((r) => { const p = kpiOf(r, "laboratoire", "taux_positivite"); return p ? p.d : null; });
    let deltaCumul = 0, nDelta = 0;
    provsSem.forEach((p) => {
      const vs = rowsSem.filter((r) => r.province === p && isNum(cleNum(r, "cumul_confirmes"))).sort((a, b) => a.date.localeCompare(b.date));
      if (vs.length > 1) { deltaCumul += cleNum(vs[vs.length - 1], "cumul_confirmes") - cleNum(vs[0], "cumul_confirmes"); nDelta++; }
    });
    const scores = rowsSem.map((r) => (r.fiabilite || {}).score).filter(isNum);
    const nCtrl = rowsSem.reduce((a, r) => a + (r.controles || []).filter((c) => c.niveau !== "info").length, 0);
    const tuiles = [
      ["Jours couverts", `${jours.length}`, `${rowsSem.length} présentations · ${provsSem.length} provinces`],
      ["Cas confirmés de la semaine", fmt(casSem), `somme des cas du jour · ${nAvec((r) => cleNum(r, "cas_jour"))} présentations`],
      ["Hausse du cumul des confirmés", nDelta ? `${deltaCumul >= 0 ? "+" : ""}${fmt(deltaCumul)}` : "–", nDelta ? `du premier au dernier jour · ${nDelta} province(s)` : "il faut au moins 2 jours"],
      ["Alertes de la semaine", fmt(alertesSem), "somme des alertes du jour"],
      ["Taux de positivité", fmtPct(pct(posSem, testSem)), testSem ? `${fmt(posSem)} positifs / ${fmt(testSem)} analysés` : "non calculable"],
      ["Fiabilité moyenne", scores.length ? `${Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)}/100` : "–", `${fmt(nCtrl)} contrôle(s) à vérifier`],
    ];
    document.getElementById("week-kpis").innerHTML = tuiles.map(([l, v, sub]) =>
      `<div class="kpi"><div class="label">${esc(l)}</div><div class="value">${v}</div><div class="sub">${esc(sub)}</div></div>`).join("");

    // ── une fenêtre par pilier
    const joursProv = (p) => new Set(rowsSem.filter((r) => r.province === p).map((r) => r.date)).size;
    const blocs = pillarOrder().filter((k) => !pilF || k === pilF).map((k, idx) => {
      const pls = rowsSem.flatMap((r) => (r.piliers || []).filter((pl) => pl.id === k).map((pl) => ({ r, pl })));
      const kpiHtml = (k === "coordination" || KPI_PILIERS.includes(k)) && !secF ? weekKpiTable(rowsSem, jours, k) : "";
      const secs = Object.keys(SECTION_NAMES).filter((sk) => !secF || sk === secF).map((sk) => {
        const items = pls.flatMap(({ r, pl }) => (pl.sections[sk] || []).map((it) => ({ ...it, province: r.province, date: r.date, n: r.n_methodes })));
        if (!items.length) return "";
        const gs = regrouper(items).sort((a, b) => b.dates.length - a.dates.length || a.province.localeCompare(b.province, "fr"));
        return `<h5 class="sec-${sk}">${esc(SECTION_NAMES[sk])} <span class="count">${gs.length}</span></h5><ul>`
          + gs.map((g) => {
            const nj = g.dates.length, tot = joursProv(g.province);
            const persist = sk === "defis" && tot > 1 && nj === tot;
            const badge = nj > 1 ? `<span class="rep${persist ? " persist" : ""}" title="${esc("Repris le " + g.dates.map(jourCourt).join(", "))}">${persist ? "persistant · " : ""}${nj} j.</span>` : `<span class="ref">${esc(jourCourt(g.date))}</span>`;
            return `<li><span class="prov-tag">${esc(g.province)}</span> ${esc(g.t)} ${badge}${g.o ? " " + OCR_TAG : ""}</li>`;
          }).join("") + "</ul>";
      }).join("");
      if (!kpiHtml && !secs) return "";
      const provsP = [...new Set(pls.map(({ r }) => r.province))];
      const nItems = pls.reduce((a, { pl }) => a + Object.values(pl.sections || {}).reduce((b, l) => b + l.length, 0), 0);
      return `<details class="week-pillar card"${idx < 2 || pilF ? " open" : ""}><summary><strong>${esc(EXT_LABELS.piliers[k])}</strong>`
        + ` <span class="muted">${provsP.length} province(s) · ${fmt(nItems)} élément(s) sur la semaine</span></summary>`
        + `${kpiHtml}${secs || (kpiHtml ? "" : "")}</details>`;
    }).join("");
    root.innerHTML = blocs || `<p class="empty">Aucun élément pour cette sélection sur la semaine.</p>`;
  }

  // ── Dispatch ──────────────────────────────────────────────
  const RENDER = { overview: renderSnapshot, summary: renderOverview, zones: renderZones, trends: renderTrends, alerts: renderAlerts, quality: renderQuality, province: renderProvince, pillars: renderPillars, kpis: renderKpis, week: renderWeek };
  function render() {
    hideTip();
    if (!DATES.length) {
      document.getElementById("main").insertAdjacentHTML("beforeend", '<p class="empty">Aucune donnée : build/manifest.json introuvable au moment du build.</p>');
      return;
    }
    renderTracker();
    (RENDER[VIEW] || (() => {}))();
  }

  initDateSelect();
  initProvinceMenu();
  // téléphone : l'onglet actif est ramené au centre de la bande d'onglets qui défile
  (() => {
    const strip = document.querySelector(".tab-links"), act = strip && strip.querySelector(".tab.active");
    if (strip && act && strip.scrollWidth > strip.clientWidth) strip.scrollLeft = act.offsetLeft - (strip.clientWidth - act.offsetWidth) / 2;
  })();
  initMapControls(() => render());
  const provinces = META.provinces || [];
  if (VIEW === "zones") getZoneProvince = initChips(document.getElementById("province-filter"), provinces, render);
  if (VIEW === "alerts") getAlertProvince = initChips(document.getElementById("province-filter"), provinces, render);
  render();
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (VIEW !== "overview") render(); else if (LMAP) LMAP.update({ focus: atDate(P.summary, DATE).map((r) => r.province) }); }, 150);
  });
})();
