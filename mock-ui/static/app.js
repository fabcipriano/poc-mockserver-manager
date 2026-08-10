const API_BASE = "/mock-ui/api/mocks";

const form = document.getElementById("mock-form");
const formTitle = document.getElementById("form-title");
const submitButton = document.getElementById("submit-button");
const cancelEditButton = document.getElementById("cancel-edit");
const formError = document.getElementById("form-error");

const idField = document.getElementById("mock-id");
const methodField = document.getElementById("mock-method");
const pathField = document.getElementById("mock-path");
const statusField = document.getElementById("mock-status");
const responseBodyField = document.getElementById("mock-response-body");

const matchersSection = document.getElementById("matchers-section");
const requestBodyField = document.getElementById("mock-request-body");
const requestBodyMatchTypeField = document.getElementById("mock-request-body-match-type");
const kvRowTemplate = document.getElementById("kv-row-template");

const KV_SECTIONS = {
  pathParameters: "path-parameters-rows",
  queryStringParameters: "query-parameters-rows",
  headers: "header-rows",
  cookies: "cookie-rows",
};

const tableBody = document.getElementById("mocks-body");
const emptyState = document.getElementById("empty-state");
const refreshButton = document.getElementById("refresh-button");

const successBanner = document.getElementById("success-banner");
const successBannerText = document.getElementById("success-banner-text");
const successBannerDismiss = document.getElementById("success-banner-dismiss");

// --- navigation ---

const VALID_PAGES = ["create", "list", "requests", "help"];
let successBannerTimeout = null;

function getCurrentPageFromHash() {
  const page = window.location.hash.replace(/^#/, "");
  return VALID_PAGES.includes(page) ? page : "create";
}

function showPage(pageName) {
  const page = VALID_PAGES.includes(pageName) ? pageName : "create";
  for (const name of VALID_PAGES) {
    document.getElementById(`page-${name}`).hidden = name !== page;
  }
  for (const link of document.querySelectorAll(".nav-link")) {
    link.classList.toggle("active", link.dataset.page === page);
  }
}

function hideSuccessBanner() {
  successBanner.hidden = true;
  if (successBannerTimeout) {
    clearTimeout(successBannerTimeout);
    successBannerTimeout = null;
  }
}

function showSuccessBanner(message) {
  successBannerText.textContent = message;
  successBanner.hidden = false;
  if (successBannerTimeout) {
    clearTimeout(successBannerTimeout);
  }
  successBannerTimeout = setTimeout(hideSuccessBanner, 4000);
}

successBannerDismiss.addEventListener("click", hideSuccessBanner);
window.addEventListener("hashchange", () => {
  const page = getCurrentPageFromHash();
  showPage(page);
  syncRequestsPageStream(page);
});

function showError(message) {
  formError.textContent = message;
  formError.hidden = false;
}

function clearError() {
  formError.hidden = true;
  formError.textContent = "";
}

// --- dynamic name/value row helpers, shared by path params, query params, headers, cookies ---

function addKvRow(containerId, name = "", value = "") {
  const container = document.getElementById(containerId);
  const row = kvRowTemplate.content.firstElementChild.cloneNode(true);
  row.querySelector(".kv-name").value = name;
  row.querySelector(".kv-value").value = value;
  row.querySelector(".remove-row").addEventListener("click", () => row.remove());
  container.appendChild(row);
}

function clearKvRows(containerId) {
  document.getElementById(containerId).innerHTML = "";
}

function getKvRows(containerId) {
  const rows = document.querySelectorAll(`#${containerId} .kv-row`);
  const pairs = [];
  for (const row of rows) {
    const name = row.querySelector(".kv-name").value.trim();
    const value = row.querySelector(".kv-value").value;
    if (name) {
      pairs.push({ name, value });
    }
  }
  return pairs;
}

document.querySelectorAll(".add-row").forEach((button) => {
  button.addEventListener("click", () => addKvRow(button.dataset.target));
});

// --- form lifecycle ---

function resetForm() {
  idField.value = "";
  form.reset();
  statusField.value = 200;
  formTitle.textContent = "Create a mock";
  submitButton.textContent = "Create mock";
  cancelEditButton.hidden = true;
  clearError();

  for (const containerId of Object.values(KV_SECTIONS)) {
    clearKvRows(containerId);
  }
  requestBodyField.value = "";
  requestBodyMatchTypeField.value = "ONLY_MATCHING_FIELDS";
  matchersSection.open = false;
}

function startEdit(mock) {
  idField.value = mock.id;
  methodField.value = mock.method;
  pathField.value = mock.path;
  statusField.value = mock.statusCode;
  responseBodyField.value = mock.responseBody === undefined ? "" : JSON.stringify(mock.responseBody, null, 2);
  formTitle.textContent = `Edit mock ${mock.id}`;
  submitButton.textContent = "Save changes";
  cancelEditButton.hidden = false;
  clearError();

  for (const [field, containerId] of Object.entries(KV_SECTIONS)) {
    clearKvRows(containerId);
    for (const pair of mock[field] || []) {
      addKvRow(containerId, pair.name, pair.value);
    }
  }
  requestBodyField.value = mock.requestBody === undefined || mock.requestBody === null ? "" : JSON.stringify(mock.requestBody, null, 2);
  requestBodyMatchTypeField.value = mock.requestBodyMatchType || "ONLY_MATCHING_FIELDS";
  matchersSection.open = (mock.matcherCount || 0) > 0;

  window.location.hash = "create";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderMocks(mocks) {
  tableBody.innerHTML = "";
  emptyState.hidden = mocks.length > 0;

  for (const mock of mocks) {
    const row = document.createElement("tr");

    const bodyPreview = mock.responseBody === undefined ? "" : JSON.stringify(mock.responseBody);
    const matcherBadge = mock.matcherCount > 0 ? `<span class="badge">+${mock.matcherCount} matcher${mock.matcherCount === 1 ? "" : "s"}</span>` : "";

    row.innerHTML = `
      <td>${mock.method}</td>
      <td><code>${mock.path}</code></td>
      <td>${mock.statusCode}</td>
      <td><code class="body-preview">${bodyPreview}</code></td>
      <td>${matcherBadge}</td>
      <td>
        <button type="button" data-action="edit">Edit</button>
        <button type="button" data-action="delete">Delete</button>
      </td>
    `;

    row.querySelector('[data-action="edit"]').addEventListener("click", () => startEdit(mock));
    row.querySelector('[data-action="delete"]').addEventListener("click", () => deleteMock(mock.id));

    tableBody.appendChild(row);
  }
}

async function loadMocks() {
  const response = await fetch(API_BASE);
  if (!response.ok) {
    throw new Error(`failed to list mocks: ${response.status}`);
  }
  const mocks = await response.json();
  renderMocks(mocks);
}

async function deleteMock(id) {
  if (!window.confirm("Delete this mock? This can't be undone.")) {
    return;
  }
  const response = await fetch(`${API_BASE}/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    throw new Error(`failed to delete mock: ${response.status}`);
  }
  if (idField.value === id) {
    resetForm();
  }
  await loadMocks();
}

function parseOptionalJson(rawValue, fieldLabel) {
  const trimmed = rawValue.trim();
  if (trimmed === "") {
    return { present: false, value: undefined };
  }
  try {
    return { present: true, value: JSON.parse(trimmed) };
  } catch (err) {
    throw new Error(`${fieldLabel} must be valid JSON (or left empty).`);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  let responseBody;
  let requestBody;
  try {
    responseBody = parseOptionalJson(responseBodyField.value, "Response body");
    requestBody = parseOptionalJson(requestBodyField.value, "Request body matcher");
  } catch (err) {
    showError(err.message);
    return;
  }

  const payload = {
    method: methodField.value,
    path: pathField.value,
    statusCode: Number(statusField.value),
    responseBody: responseBody.present ? responseBody.value : {},
    pathParameters: getKvRows(KV_SECTIONS.pathParameters),
    queryStringParameters: getKvRows(KV_SECTIONS.queryStringParameters),
    headers: getKvRows(KV_SECTIONS.headers),
    cookies: getKvRows(KV_SECTIONS.cookies),
  };

  if (requestBody.present) {
    payload.requestBody = requestBody.value;
    payload.requestBodyMatchType = requestBodyMatchTypeField.value;
  }

  const editingId = idField.value;
  const url = editingId ? `${API_BASE}/${encodeURIComponent(editingId)}` : API_BASE;
  const method = editingId ? "PUT" : "POST";

  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    showError(detail.error || `request failed: ${response.status}`);
    return;
  }

  const wasEditing = Boolean(editingId);
  resetForm();
  await loadMocks();
  window.location.hash = "list";
  showSuccessBanner(wasEditing ? "Mock updated." : "Mock created.");
});

cancelEditButton.addEventListener("click", () => {
  resetForm();
  window.location.hash = "list";
});
refreshButton.addEventListener("click", () => loadMocks().catch((err) => showError(err.message)));

// --- Recent Requests page: history load, live tail (SSE), path filter, pause/resume ---

const requestsBody = document.getElementById("requests-body");
const requestsEmptyState = document.getElementById("requests-empty-state");
const requestsPathFilter = document.getElementById("requests-path-filter");
const requestsStatusFilter = document.getElementById("requests-status-filter");
const requestsFromFilter = document.getElementById("requests-from-filter");
const requestsToFilter = document.getElementById("requests-to-filter");
const requestsPauseToggle = document.getElementById("requests-pause-toggle");
const requestsError = document.getElementById("requests-error");
const requestsRangeTruncated = document.getElementById("requests-range-truncated");
const requestsLoadMoreButton = document.getElementById("requests-load-more");
const requestsNoMoreMessage = document.getElementById("requests-no-more");

let requestsEventSource = null;
let requestsPaused = false;
let requestsPendingQueue = [];
let requestsFilterDebounce = null;
let requestsOldestLoadedTimestamp = null;
let requestsHasMore = false;

function showRequestsError(message) {
  requestsError.textContent = message;
  requestsError.hidden = false;
}

function clearRequestsError() {
  requestsError.hidden = true;
  requestsError.textContent = "";
}

function currentRequestsPathFilter() {
  return requestsPathFilter.value.trim();
}

function requestsApiUrl(basePath, { before, includeTimeRange = true } = {}) {
  const params = new URLSearchParams();
  const path = currentRequestsPathFilter();
  if (path) {
    params.set("path", path);
  }
  if (requestsStatusFilter.value) {
    params.set("mocked", requestsStatusFilter.value);
  }
  // The live tail (includeTimeRange: false) deliberately ignores from/to - a newly arriving
  // request is always "now," so a historical time range doesn't scope it. See design.md.
  if (includeTimeRange) {
    if (requestsFromFilter.value) {
      params.set("from", requestsFromFilter.value);
    }
    if (requestsToFilter.value) {
      params.set("to", requestsToFilter.value);
    }
  }
  if (before) {
    params.set("before", before);
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

function escapeHtml(value) {
  if (value === undefined || value === null) {
    return "";
  }
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatBody(body) {
  if (body === undefined || body === null || body === "") {
    return "(empty)";
  }
  if (typeof body === "string") {
    return body;
  }
  try {
    return JSON.stringify(body, null, 2);
  } catch {
    return String(body);
  }
}

function renderHeaderRows(pairs) {
  if (!pairs || pairs.length === 0) {
    return `<tr><td colspan="2" class="requests-detail-empty">(none)</td></tr>`;
  }
  return pairs
    .map((pair) => `<tr><td>${escapeHtml(pair.name)}</td><td>${escapeHtml(pair.value)}</td></tr>`)
    .join("");
}

function renderRequestDetailRow(entry) {
  const detailRow = document.createElement("tr");
  detailRow.className = "requests-detail-row";
  detailRow.hidden = true;
  detailRow.innerHTML = `
    <td colspan="6">
      <div class="requests-detail">
        <div class="requests-detail-column">
          <h3>Request</h3>
          <h4>Headers</h4>
          <table class="requests-detail-headers"><tbody>${renderHeaderRows(entry.requestHeaders)}</tbody></table>
          <h4>Body</h4>
          <pre class="requests-detail-body">${escapeHtml(formatBody(entry.requestBody))}</pre>
        </div>
        <div class="requests-detail-column">
          <h3>Response</h3>
          <h4>Headers</h4>
          <table class="requests-detail-headers"><tbody>${renderHeaderRows(entry.responseHeaders)}</tbody></table>
          <h4>Body</h4>
          <pre class="requests-detail-body">${escapeHtml(formatBody(entry.responseBody))}</pre>
        </div>
      </div>
    </td>
  `;
  return detailRow;
}

function renderRequestRow(entry, detailRow) {
  const row = document.createElement("tr");
  row.className = "requests-row";
  const sourceLabel = entry.mocked ? "Mocked" : "Forwarded";
  const sourceClass = entry.mocked ? "requests-source-mocked" : "requests-source-forwarded";
  row.innerHTML = `
    <td>${escapeHtml(entry.timestamp)}</td>
    <td>${escapeHtml(entry.method)}</td>
    <td><code>${escapeHtml(entry.path)}</code></td>
    <td>${escapeHtml(entry.statusCode)}</td>
    <td><span class="badge ${sourceClass}">${sourceLabel}</span></td>
    <td><button type="button" class="requests-expand-toggle" aria-expanded="false">Details</button></td>
  `;
  row.querySelector(".requests-expand-toggle").addEventListener("click", (event) => {
    const expanded = !detailRow.hidden;
    detailRow.hidden = expanded;
    event.currentTarget.setAttribute("aria-expanded", String(!expanded));
    event.currentTarget.textContent = expanded ? "Details" : "Hide";
  });
  return row;
}

function updateRequestsEmptyState() {
  requestsEmptyState.hidden = requestsBody.children.length > 0;
}

function updateRequestsPaginationUI() {
  const hasRows = requestsBody.children.length > 0;
  requestsLoadMoreButton.hidden = !requestsHasMore;
  requestsNoMoreMessage.hidden = requestsHasMore || !hasRows;
}

function updateRequestsRangeTruncatedNotice(rangeTruncated, oldestAvailableTimestamp) {
  if (rangeTruncated && oldestAvailableTimestamp) {
    requestsRangeTruncated.textContent = `Showing requests back to ${oldestAvailableTimestamp} - earlier requests are no longer retained by MockServer.`;
    requestsRangeTruncated.hidden = false;
  } else {
    requestsRangeTruncated.hidden = true;
    requestsRangeTruncated.textContent = "";
  }
}

function appendRequestRow(entry) {
  const detailRow = renderRequestDetailRow(entry);
  requestsBody.appendChild(renderRequestRow(entry, detailRow));
  requestsBody.appendChild(detailRow);
}

function prependRequestRow(entry) {
  const detailRow = renderRequestDetailRow(entry);
  const summaryRow = renderRequestRow(entry, detailRow);
  requestsBody.insertBefore(detailRow, requestsBody.firstChild);
  requestsBody.insertBefore(summaryRow, detailRow);
  updateRequestsEmptyState();
}

async function loadRequestHistory() {
  const response = await fetch(requestsApiUrl("/mock-ui/api/requests"));
  if (!response.ok) {
    throw new Error(`failed to load recent requests: ${response.status}`);
  }
  const data = await response.json();
  requestsBody.innerHTML = "";
  for (const entry of data.entries) {
    appendRequestRow(entry);
  }
  requestsOldestLoadedTimestamp = data.entries.length > 0 ? data.entries[data.entries.length - 1].timestamp : null;
  requestsHasMore = data.hasMore;
  updateRequestsEmptyState();
  updateRequestsPaginationUI();
  updateRequestsRangeTruncatedNotice(data.rangeTruncated, data.oldestAvailableTimestamp);
}

async function loadMoreRequests() {
  if (!requestsOldestLoadedTimestamp) {
    return;
  }
  const response = await fetch(requestsApiUrl("/mock-ui/api/requests", { before: requestsOldestLoadedTimestamp }));
  if (!response.ok) {
    throw new Error(`failed to load older requests: ${response.status}`);
  }
  const data = await response.json();
  for (const entry of data.entries) {
    appendRequestRow(entry);
  }
  if (data.entries.length > 0) {
    requestsOldestLoadedTimestamp = data.entries[data.entries.length - 1].timestamp;
  }
  requestsHasMore = data.hasMore;
  updateRequestsPaginationUI();
}

function closeRequestsStream() {
  if (requestsEventSource) {
    requestsEventSource.close();
    requestsEventSource = null;
  }
}

function openRequestsStream() {
  closeRequestsStream();
  requestsEventSource = new EventSource(requestsApiUrl("/mock-ui/api/requests/stream", { includeTimeRange: false }));
  requestsEventSource.onmessage = (event) => {
    const entry = JSON.parse(event.data);
    if (requestsPaused) {
      requestsPendingQueue.push(entry);
    } else {
      prependRequestRow(entry);
    }
  };
  requestsEventSource.onerror = () => {
    showRequestsError("Lost connection to the live request stream. Reopen the Recent Requests page to reconnect.");
  };
}

function syncRequestsPageStream(page) {
  if (page === "requests") {
    if (!requestsEventSource) {
      clearRequestsError();
      loadRequestHistory().catch((err) => showRequestsError(err.message));
      openRequestsStream();
    }
  } else {
    closeRequestsStream();
  }
}

requestsPauseToggle.addEventListener("click", () => {
  requestsPaused = !requestsPaused;
  requestsPauseToggle.textContent = requestsPaused ? "Resume" : "Pause";
  requestsPauseToggle.classList.toggle("paused", requestsPaused);
  if (!requestsPaused) {
    for (const entry of requestsPendingQueue) {
      prependRequestRow(entry);
    }
    requestsPendingQueue = [];
  }
});

function reloadRequestsForFilterChange() {
  clearRequestsError();
  requestsPendingQueue = [];
  loadRequestHistory().catch((err) => showRequestsError(err.message));
  openRequestsStream();
}

requestsPathFilter.addEventListener("input", () => {
  if (requestsFilterDebounce) {
    clearTimeout(requestsFilterDebounce);
  }
  requestsFilterDebounce = setTimeout(reloadRequestsForFilterChange, 300);
});

requestsStatusFilter.addEventListener("change", reloadRequestsForFilterChange);
requestsFromFilter.addEventListener("change", reloadRequestsForFilterChange);
requestsToFilter.addEventListener("change", reloadRequestsForFilterChange);

requestsLoadMoreButton.addEventListener("click", () => {
  loadMoreRequests().catch((err) => showRequestsError(err.message));
});

const initialPage = getCurrentPageFromHash();
showPage(initialPage);
syncRequestsPageStream(initialPage);
loadMocks().catch((err) => showError(err.message));
