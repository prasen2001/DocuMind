const state = { documents: [], active: null, page: 1, view: "page", citations: [] };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const type = response.headers.get("content-type") || "";
  const body = type.includes("json") ? await response.json() : null;
  if (!response.ok) throw new Error(body?.error || `Request failed (${response.status})`);
  return body;
}

function escapeHtml(value = "") {
  const node = document.createElement("span");
  node.textContent = value;
  return node.innerHTML;
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.remove("hidden");
  clearTimeout(toast.timeout);
  toast.timeout = setTimeout(() => element.classList.add("hidden"), 3200);
}

const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

async function waitForJob(jobId) {
  for (let attempt = 0; attempt < 1200; attempt++) {
    const job = await api(`/api/jobs/${jobId}`);
    if (job.status === "ready") return job;
    if (job.status === "failed") throw new Error(job.error || "Document processing failed");
    await pause(250);
  }
  throw new Error("Document processing did not finish within five minutes");
}

async function loadDocuments(selectFirst = true) {
  const result = await api("/api/documents");
  state.documents = result.documents;
  renderDocumentList();
  if (selectFirst && !state.active && state.documents.length) await selectDocument(state.documents[0].id);
  if (!state.documents.length) showWelcome();
}

function renderDocumentList() {
  $("#document-list").innerHTML = state.documents.map(doc => `
    <button class="document-card ${state.active?.id === doc.id ? "active" : ""}" data-id="${doc.id}">
      <span class="file-glyph">▱</span>
      <strong>${escapeHtml(doc.filename)}</strong>
      <small>${doc.summary.page_count} pages · ${formatBytes(doc.size_bytes)}</small>
    </button>`).join("");
  $$(".document-card").forEach(button => button.addEventListener("click", () => selectDocument(button.dataset.id)));
}

function showWelcome() {
  $("#welcome").classList.remove("hidden");
  $("#workspace").classList.add("hidden");
}

function showWorkspace() {
  $("#welcome").classList.add("hidden");
  $("#workspace").classList.remove("hidden");
}

async function upload(file) {
  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    $("#welcome-error").textContent = "Please choose a PDF file.";
    $("#welcome-error").classList.remove("hidden");
    return;
  }
  $("#welcome-error").classList.add("hidden");
  $("#upload-progress").classList.remove("hidden");
  try {
    const job = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/pdf", "X-Filename": encodeURIComponent(file.name) },
      body: file,
    });
    const completed = await waitForJob(job.id);
    const document = await api(`/api/documents/${completed.document_id}`);
    state.active = document;
    state.page = 1;
    await loadDocuments(false);
    renderActiveDocument();
    showWorkspace();
    toast(`${file.name} is ready`);
  } catch (error) {
    $("#welcome-error").textContent = error.message;
    $("#welcome-error").classList.remove("hidden");
    toast(error.message);
  } finally {
    $("#upload-progress").classList.add("hidden");
    $("#file-input").value = "";
    $("#sidebar-file").value = "";
  }
}

async function selectDocument(id) {
  state.active = await api(`/api/documents/${id}`);
  state.page = 1;
  state.citations = [];
  renderDocumentList();
  renderActiveDocument();
  showWorkspace();
}

function renderActiveDocument() {
  const doc = state.active;
  $("#document-title").textContent = doc.filename;
  $("#page-count").textContent = doc.summary.page_count;
  $("#document-stats").innerHTML = [
    [doc.summary.page_count, "Pages"], [doc.summary.table_count, "Tables"],
    [doc.summary.chart_count ?? 0, "Charts"], [doc.summary.image_count, "Images"],
    [doc.summary.ocr_required_pages ?? doc.summary.ocr_pages, "OCR needed"],
  ].map(([value, label]) => `<div class="stat"><strong>${value}</strong><small>${label}</small></div>`).join("");
  $("#answer-result").classList.add("hidden");
  $("#answer-empty").classList.remove("hidden");
  $("#suggestions").innerHTML = ["What is this document about?", "What dates are mentioned?", "What are the key terms?"]
    .map(question => `<button class="suggestion">${question}</button>`).join("");
  $$(".suggestion").forEach(button => button.addEventListener("click", () => ask(button.textContent)));
  renderPage();
}

function renderPage() {
  const page = state.active.pages[state.page - 1];
  $("#page-number").textContent = state.page;
  $("#prev-page").disabled = state.page === 1;
  $("#next-page").disabled = state.page === state.active.pages.length;
  $("#page-image").src = `/api/documents/${state.active.id}/pages/${state.page}.png`;
  renderHighlights(page);
  renderStructure(page);
  renderTables(page);
  renderCharts(page);
}

function renderHighlights(page) {
  const citations = state.citations.filter(citation => citation.page === state.page);
  $("#evidence-layer").innerHTML = citations.map(citation => {
    const [x0, y0, x1, y1] = citation.bbox;
    return `<div class="highlight" style="left:${x0 / page.width * 100}%;top:${y0 / page.height * 100}%;width:${(x1-x0) / page.width * 100}%;height:${(y1-y0) / page.height * 100}%"></div>`;
  }).join("");
}

function renderStructure(page) {
  const regions = page.regions.length ? page.regions.map(region => `
    <div class="region-card"><span>${escapeHtml(region.type)}</span><p>${escapeHtml(region.text || "[Embedded image]")}</p></div>
  `).join("") : `<div class="empty-state">No structured regions were found on this page.</div>`;
  const relationships = page.relationships?.length ? `<div class="eyebrow" style="margin-top:24px">Relationships</div>${page.relationships.map(link => `
    <div class="region-card"><span>${escapeHtml(link.type)}</span><p>${escapeHtml(link.source_id)} → ${escapeHtml(link.target_id)} · ${Math.round(link.confidence * 100)}%</p></div>
  `).join("")}` : "";
  $("#structure-view").innerHTML = regions + relationships;
}

function renderTables(page) {
  $("#tables-view").innerHTML = page.tables.length ? page.tables.map((table, index) => `
    <div class="table-wrap"><div class="eyebrow">Table ${index + 1} · ${table.row_count} × ${table.column_count}</div>
      <table><tbody>${table.rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>
    </div>`).join("") : `<div class="empty-state">No tables were detected on page ${page.number}.</div>`;
}

function renderCharts(page) {
  const charts = page.charts || [];
  $("#charts-view").innerHTML = charts.length ? charts.map((chart, index) => `
    <article class="chart-card">
      <div class="eyebrow">Chart ${index + 1}</div>
      <h4>${escapeHtml(chart.title || `${chart.type} chart`)}</h4>
      <div class="chart-meta">${escapeHtml(chart.type)} · ${Math.round(chart.confidence * 100)}% confidence · ${chart.drawing_count} vector elements</div>
      <p>${escapeHtml(chart.labels.join(" · "))}</p>
      <div class="chart-values">${chart.values.map(value => `<span class="chart-value">${escapeHtml(value.raw)}</span>`).join("")}</div>
    </article>`).join("") : `<div class="empty-state">No vector charts were detected on page ${page.number}.</div>`;
}

function switchView(view) {
  state.view = view;
  $$(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.view === view));
  ["page", "structure", "tables", "charts"].forEach(name => $(`#${name}-view`).classList.toggle("hidden", name !== view));
}

async function ask(question) {
  if (!question.trim() || !state.active) return;
  $("#question").value = question;
  const submit = $("#question-form button");
  submit.disabled = true;
  submit.textContent = "…";
  try {
    const result = await api(`/api/documents/${state.active.id}/questions`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    state.citations = result.citations;
    $("#answer-empty").classList.add("hidden");
    $("#answer-result").classList.remove("hidden");
    $("#answer-result").innerHTML = `
      <div class="grounding">${result.grounded ? `${result.citations.length} grounded source${result.citations.length === 1 ? "" : "s"}` : "No supporting evidence"}</div>
      <p class="answer-text">${escapeHtml(result.answer)}</p>
      ${result.citations.map(citation => `<div class="citation" data-page="${citation.page}">
        <strong>Page ${citation.page} · Source region</strong><p>${escapeHtml(citation.quote)}</p></div>`).join("")}`;
    $$(".citation").forEach(card => card.addEventListener("click", () => {
      state.page = Number(card.dataset.page); switchView("page"); renderPage();
      $("#page-view").scrollTo({ top: 0, behavior: "smooth" });
    }));
    if (result.citations.length) { state.page = result.citations[0].page; renderPage(); }
  } catch (error) { toast(error.message); }
  finally { submit.disabled = false; submit.textContent = "→"; }
}

async function runSearch(query) {
  if (!query.trim()) { $("#search-results").classList.add("hidden"); return; }
  try {
    const result = await api(`/api/search?q=${encodeURIComponent(query)}&limit=12`);
    const panel = $("#search-results");
    panel.innerHTML = result.matches.length ? result.matches.map(match => `
      <button class="search-result" data-document="${match.document_id}" data-page="${match.page}" data-region="${match.region_id}" data-bbox="${match.bbox.join(",")}">
        <strong>${escapeHtml(match.filename)} · Page ${match.page}</strong>
        <small>${escapeHtml(match.quote.slice(0, 150))}</small>
      </button>`).join("") : `<div class="empty-state" style="padding:18px">No matching evidence.</div>`;
    panel.classList.remove("hidden");
    $$(".search-result").forEach(button => button.addEventListener("click", async () => {
      await selectDocument(button.dataset.document);
      state.page = Number(button.dataset.page);
      state.citations = [{ page: state.page, region_id: button.dataset.region, bbox: button.dataset.bbox.split(",").map(Number) }];
      switchView("page"); renderPage(); panel.classList.add("hidden");
    }));
  } catch (error) { toast(error.message); }
}

function openComparison() {
  $("#compare-documents").innerHTML = state.documents.map((doc, index) => `
    <label class="compare-choice"><input type="checkbox" value="${doc.id}" ${index < 2 ? "checked" : ""}>
      <span>${escapeHtml(doc.filename)}<br><small>${doc.summary.page_count} pages</small></span></label>
  `).join("");
  $("#compare-results").innerHTML = "";
  $("#compare-modal").classList.remove("hidden");
}

async function runComparison() {
  const documentIds = $$("#compare-documents input:checked").map(input => input.value);
  if (documentIds.length < 2) { toast("Choose at least two documents"); return; }
  const button = $("#compare-form button");
  button.disabled = true; button.textContent = "Comparing…";
  try {
    const result = await api("/api/compare", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: documentIds, question: $("#compare-question").value }),
    });
    const common = result.common_terms.length ? `Shared terms: ${result.common_terms.join(", ")}` : "No shared terms were found across the grounded answers.";
    $("#compare-results").innerHTML = `<div class="compare-summary">${result.grounded_document_count} of ${result.document_count} documents contain matching evidence. ${escapeHtml(common)}</div>
      ${result.results.map(item => `<article class="compare-result"><h4>${escapeHtml(item.filename)}</h4><p>${escapeHtml(item.answer)}</p>
        ${item.citations.map(citation => `<button class="compare-citation" data-document="${item.document_id}" data-page="${citation.page}">Page ${citation.page}: ${escapeHtml(citation.quote.slice(0, 90))}</button>`).join("<br>")}
      </article>`).join("")}`;
    $$(".compare-citation").forEach(citation => citation.addEventListener("click", async () => {
      await selectDocument(citation.dataset.document);
      state.page = Number(citation.dataset.page); renderPage();
      $("#compare-modal").classList.add("hidden");
    }));
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; button.textContent = "Compare"; }
}

$("#file-input").addEventListener("change", event => upload(event.target.files[0]));
$("#sidebar-file").addEventListener("change", event => upload(event.target.files[0]));
const dropzone = $("#dropzone");
["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", event => upload(event.dataTransfer.files[0]));
$("#prev-page").addEventListener("click", () => { if (state.page > 1) { state.page--; renderPage(); } });
$("#next-page").addEventListener("click", () => { if (state.page < state.active.pages.length) { state.page++; renderPage(); } });
$$(".tab").forEach(tab => tab.addEventListener("click", () => switchView(tab.dataset.view)));
$("#question-form").addEventListener("submit", event => { event.preventDefault(); ask($("#question").value); });
$("#search-form").addEventListener("submit", event => { event.preventDefault(); runSearch($("#search-query").value); });
[$("#compare-open"), $("#compare-header-open")].forEach(button => button.addEventListener("click", () => {
  if (state.documents.length < 2) { toast("Upload at least two documents to compare"); return; }
  openComparison();
}));
$("#compare-close").addEventListener("click", () => $("#compare-modal").classList.add("hidden"));
$("#compare-modal").addEventListener("click", event => { if (event.target === $("#compare-modal")) $("#compare-modal").classList.add("hidden"); });
$("#compare-form").addEventListener("submit", event => { event.preventDefault(); runComparison(); });

loadDocuments().catch(error => { showWelcome(); toast(`Could not load workspace: ${error.message}`); });

