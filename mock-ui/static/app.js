const API_BASE = "/mock-ui/api/mocks";
const SERVERS_API = "/mock-ui/api/servers";

const serverSelect = document.getElementById("server-select");

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

// --- MockServer target selection ---
//
// The selected target is kept in the `server` URL query param (not localStorage) so it's
// visible, shareable, and consistent with how page routing already works via location.hash -
// see design.md's "Frontend: a persistent target selector" decision.

let currentServer = null;

function withServer(url) {
  if (!currentServer) {
    return url;
  }
  const params = new URLSearchParams();
  params.set("server", currentServer);
  const query = params.toString();
  return url.includes("?") ? `${url}&${query}` : `${url}?${query}`;
}

function serverIdFromUrl() {
  return new URLSearchParams(window.location.search).get("server");
}

function updateServerInUrl(serverId) {
  const url = new URL(window.location.href);
  url.searchParams.set("server", serverId);
  history.replaceState(null, "", url.toString());
}

async function loadServers() {
  const response = await fetch(SERVERS_API);
  if (!response.ok) {
    throw new Error(`failed to load MockServer targets: ${response.status}`);
  }
  const servers = await response.json();

  serverSelect.innerHTML = "";
  for (const server of servers) {
    const option = document.createElement("option");
    option.value = server.id;
    option.textContent = server.label;
    serverSelect.appendChild(option);
  }

  const requestedServer = serverIdFromUrl();
  const knownIds = servers.map((server) => server.id);
  currentServer = knownIds.includes(requestedServer) ? requestedServer : (servers[0] ? servers[0].id : null);
  serverSelect.value = currentServer;
  if (currentServer) {
    updateServerInUrl(currentServer);
  }
}

function onServerChanged() {
  currentServer = serverSelect.value;
  updateServerInUrl(currentServer);
  resetForm();
  loadMocks().catch((err) => showError(err.message));
  if (getCurrentPageFromHash() === "requests") {
    reloadRequestsForFilterChange();
  }
  if (getCurrentPageFromHash() === "generate") {
    syncGeneratePage("generate");
  }
}

serverSelect.addEventListener("change", onServerChanged);

// --- navigation ---

const VALID_PAGES = ["create", "list", "requests", "generate", "help"];
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
  syncGeneratePage(page);
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
  const response = await fetch(withServer(API_BASE));
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
  const response = await fetch(withServer(`${API_BASE}/${encodeURIComponent(id)}`), { method: "DELETE" });
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
  const url = withServer(editingId ? `${API_BASE}/${encodeURIComponent(editingId)}` : API_BASE);
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
const requestsConnectionStatus = document.getElementById("requests-connection-status");
const requestsConnectionStatusLabel = requestsConnectionStatus.querySelector(".connection-status-label");
const requestsResyncNotice = document.getElementById("requests-resync-notice");

let requestsEventSource = null;
let requestsPaused = false;
let requestsPendingQueue = [];
let requestsFilterDebounce = null;
let requestsOldestLoadedTimestamp = null;
let requestsHasMore = false;
let requestsReconnectTimer = null;
let requestsReconnectAttempt = 0;
let requestsResyncNoticeTimer = null;

const REQUESTS_RESYNC_NOTICE_DURATION_MS = 6000;

function showRequestsResyncNotice(reasonText) {
  if (requestsResyncNoticeTimer) {
    clearTimeout(requestsResyncNoticeTimer);
  }
  requestsResyncNotice.textContent = reasonText;
  requestsResyncNotice.hidden = false;
  requestsResyncNoticeTimer = setTimeout(() => {
    requestsResyncNotice.hidden = true;
    requestsResyncNoticeTimer = null;
  }, REQUESTS_RESYNC_NOTICE_DURATION_MS);
}

// Shared by both the "reconnect succeeded" and "server detected a MockServer-side reset"
// triggers - both need the same outcome: refresh the table from current server state and
// tell the developer why. See design.md's "one shared resync helper" decision.
async function resyncRequestsHistory(reasonText) {
  console.log(`[requests] resyncing history: ${reasonText}`);
  try {
    await loadRequestHistory();
    showRequestsResyncNotice(reasonText);
  } catch (err) {
    showRequestsError(err.message);
  }
}

// Capped exponential backoff for live tail reconnection - see design.md's reconnection
// decision. The connection never permanently gives up; Disconnected just means the last
// several attempts failed, while attempts keep retrying in the background.
const REQUESTS_RECONNECT_BASE_DELAY_MS = 1000;
const REQUESTS_RECONNECT_MAX_DELAY_MS = 30000;
const REQUESTS_DISCONNECTED_THRESHOLD = 5;
// Bounds the live tail's own DOM growth - independent of REQUEST_HISTORY_LIMIT, which only
// bounds one page's fetch cost from mock-ui's backend. Without this, a tab left open during
// sustained traffic accumulates rows (2 DOM nodes each) without limit. See design.md in
// openspec/changes/cap-recent-requests-live-tail-rows.
const LIVE_TAIL_MAX_ROWS = 500;
const REQUESTS_CONNECTION_STATE_LABELS = {
  connecting: "Connecting…",
  live: "Live",
  reconnecting: "Reconnecting…",
  disconnected: "Disconnected",
};

function setRequestsConnectionState(state) {
  requestsConnectionStatus.dataset.state = state;
  requestsConnectionStatusLabel.textContent = REQUESTS_CONNECTION_STATE_LABELS[state];
}

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

function localDateTimeInputToUtcString(value) {
  if (!value) {
    return null;
  }
  // datetime-local values (e.g. "2026-08-09T14:30:00") parse as local wall-clock time;
  // reformat via the UTC accessors into the naive-UTC string the backend expects.
  const localDate = new Date(value);
  if (Number.isNaN(localDate.getTime())) {
    return null;
  }
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${localDate.getUTCFullYear()}-${pad(localDate.getUTCMonth() + 1)}-${pad(localDate.getUTCDate())} ` +
    `${pad(localDate.getUTCHours())}:${pad(localDate.getUTCMinutes())}:${pad(localDate.getUTCSeconds())}`
  );
}

function requestsApiUrl(basePath, { before, includeTimeRange = true } = {}) {
  const params = new URLSearchParams();
  if (currentServer) {
    params.set("server", currentServer);
  }
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
    const fromUtc = localDateTimeInputToUtcString(requestsFromFilter.value);
    if (fromUtc) {
      params.set("from", fromUtc);
    }
    const toUtc = localDateTimeInputToUtcString(requestsToFilter.value);
    if (toUtc) {
      params.set("to", toUtc);
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

function formatLocalTimestamp(rawUtcTimestamp) {
  if (!rawUtcTimestamp) {
    return rawUtcTimestamp;
  }
  // MockServer logs a naive "YYYY-MM-DD HH:MM:SS.ffffff" string that is actually UTC;
  // treat it as such before letting the browser render it in the viewer's own time zone.
  const parsed = new Date(rawUtcTimestamp.replace(" ", "T") + "Z");
  if (Number.isNaN(parsed.getTime())) {
    return rawUtcTimestamp;
  }
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
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
    <td>${escapeHtml(formatLocalTimestamp(entry.timestamp))}</td>
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
    requestsRangeTruncated.textContent = `Showing requests back to ${formatLocalTimestamp(oldestAvailableTimestamp)} - earlier requests are no longer retained by MockServer.`;
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
  // Rows arrive here in unbounded quantity over an unbounded amount of time (the live tail and
  // the paused-tail backlog replay), unlike appendRequestRow's page-at-a-time loads - so this is
  // the one insertion path that needs to evict, keeping the table's DOM size flat regardless of
  // arrival rate or how long the tab has been open. See design.md in
  // openspec/changes/cap-recent-requests-live-tail-rows.
  while (requestsBody.children.length > LIVE_TAIL_MAX_ROWS * 2) {
    requestsBody.removeChild(requestsBody.lastElementChild);
  }
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
  if (requestsReconnectTimer) {
    clearTimeout(requestsReconnectTimer);
    requestsReconnectTimer = null;
  }
  if (requestsEventSource) {
    console.log("[requests] closing live tail connection");
    requestsEventSource.onerror = null;
    requestsEventSource.close();
    requestsEventSource = null;
  }
  requestsReconnectAttempt = 0;
}

function scheduleRequestsReconnect() {
  requestsReconnectAttempt += 1;
  const delay = Math.min(
    REQUESTS_RECONNECT_BASE_DELAY_MS * 2 ** (requestsReconnectAttempt - 1),
    REQUESTS_RECONNECT_MAX_DELAY_MS,
  );
  console.log(`[requests] scheduling live tail reconnect attempt ${requestsReconnectAttempt} in ${delay}ms`);
  setRequestsConnectionState(requestsReconnectAttempt >= REQUESTS_DISCONNECTED_THRESHOLD ? "disconnected" : "reconnecting");
  requestsReconnectTimer = setTimeout(() => {
    requestsReconnectTimer = null;
    connectRequestsStream(true);
  }, delay);
}

function connectRequestsStream(isReconnect) {
  requestsEventSource = new EventSource(requestsApiUrl("/mock-ui/api/requests/stream", { includeTimeRange: false }));
  requestsEventSource.onopen = () => {
    console.log("[requests] live tail connected");
    requestsReconnectAttempt = 0;
    setRequestsConnectionState("live");
    if (isReconnect) {
      // The tail alone only resumes new arrivals - the table itself may still hold rows from
      // before whatever caused the drop, so a reconnect also resyncs history. See design.md.
      resyncRequestsHistory("Live tail reconnected - history refreshed to match MockServer's current state.");
    }
  };
  requestsEventSource.onmessage = (event) => {
    const entry = JSON.parse(event.data);
    if (requestsPaused) {
      requestsPendingQueue.push(entry);
    } else {
      prependRequestRow(entry);
    }
  };
  requestsEventSource.addEventListener("history-reset", () => {
    console.log("[requests] server detected a MockServer-side history reset");
    resyncRequestsHistory("MockServer's request history was reset - refreshed to match its current state.");
  });
  requestsEventSource.onerror = () => {
    const readyState = requestsEventSource ? requestsEventSource.readyState : undefined;
    console.warn(`[requests] live tail connection error (readyState=${readyState})`);
    if (requestsEventSource) {
      requestsEventSource.onerror = null;
      requestsEventSource.close();
      requestsEventSource = null;
    }
    scheduleRequestsReconnect();
  };
}

function openRequestsStream() {
  closeRequestsStream();
  setRequestsConnectionState("connecting");
  connectRequestsStream(false);
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

// --- AI Mock Generator page: select captured requests, draft candidates with an LLM, review,
// approve, and load - see openspec/changes/add-llm-mock-generation. Nothing here calls the
// generation endpoints without an explicit developer click, and nothing loads into MockServer
// without the separate "Approve & load" click.

// Must match MOCK_GENERATION_MAX_SOURCE_ENTRIES in mock-ui/app.py - kept as a client-side guard
// so a developer sees the cap before submitting, not only after a 400 comes back.
const GENERATE_MAX_SOURCE_ENTRIES = 25;

const navGenerateLink = document.getElementById("nav-generate");
const generateUnavailableNotice = document.getElementById("generate-unavailable");
const generateAvailableContent = document.getElementById("generate-available-content");
const generateSourceBody = document.getElementById("generate-source-body");
const generateSourceEmpty = document.getElementById("generate-source-empty");
const generateSelectionCount = document.getElementById("generate-selection-count");
const generateRefreshSourceButton = document.getElementById("generate-refresh-source");
const generateRunButton = document.getElementById("generate-run-button");
const generateError = document.getElementById("generate-error");
const generateResults = document.getElementById("generate-results");
const generateCandidatesContainer = document.getElementById("generate-candidates");
const generateRejectedSection = document.getElementById("generate-rejected-section");
const generateRejectedList = document.getElementById("generate-rejected-list");
const generateApproveButton = document.getElementById("generate-approve-button");
const generateLoadResult = document.getElementById("generate-load-result");

let generationAvailable = false;
let generationSourceEntries = [];
let generationSelectedIndexes = new Set();
let generationCandidates = [];

function showGenerateError(message) {
  generateError.textContent = message;
  generateError.hidden = false;
}

function clearGenerateError() {
  generateError.hidden = true;
  generateError.textContent = "";
}

async function checkMockGenerationAvailability() {
  try {
    const response = await fetch("/mock-ui/api/mock-generation/status");
    if (!response.ok) {
      throw new Error(`status check failed: ${response.status}`);
    }
    const data = await response.json();
    generationAvailable = Boolean(data.available);
  } catch (err) {
    generationAvailable = false;
  }
  navGenerateLink.hidden = !generationAvailable;
  generateUnavailableNotice.hidden = generationAvailable;
  generateAvailableContent.hidden = !generationAvailable;
}

function updateGenerateSelectionCount() {
  generateSelectionCount.textContent = `${generationSelectedIndexes.size} selected (max ${GENERATE_MAX_SOURCE_ENTRIES})`;
  generateRunButton.disabled = generationSelectedIndexes.size === 0;
}

function renderGenerateSourceList() {
  generateSourceBody.innerHTML = "";
  generateSourceEmpty.hidden = generationSourceEntries.length > 0;
  generationSourceEntries.forEach((entry, index) => {
    const row = document.createElement("tr");
    const sourceLabel = entry.mocked ? "Mocked" : "Forwarded";
    const sourceClass = entry.mocked ? "requests-source-mocked" : "requests-source-forwarded";
    row.innerHTML = `
      <td><input type="checkbox" class="generate-source-checkbox" /></td>
      <td>${escapeHtml(entry.method)}</td>
      <td><code>${escapeHtml(entry.path)}</code></td>
      <td>${escapeHtml(entry.statusCode)}</td>
      <td><span class="badge ${sourceClass}">${sourceLabel}</span></td>
    `;
    const checkbox = row.querySelector(".generate-source-checkbox");
    checkbox.checked = generationSelectedIndexes.has(index);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        if (generationSelectedIndexes.size >= GENERATE_MAX_SOURCE_ENTRIES) {
          checkbox.checked = false;
          showGenerateError(`You can select at most ${GENERATE_MAX_SOURCE_ENTRIES} requests per generation run.`);
          return;
        }
        clearGenerateError();
        generationSelectedIndexes.add(index);
      } else {
        generationSelectedIndexes.delete(index);
      }
      updateGenerateSelectionCount();
    });
    generateSourceBody.appendChild(row);
  });
  updateGenerateSelectionCount();
}

async function loadGenerateSourceEntries() {
  const response = await fetch(withServer("/mock-ui/api/requests"));
  if (!response.ok) {
    throw new Error(`failed to load recent requests: ${response.status}`);
  }
  const data = await response.json();
  generationSourceEntries = data.entries;
  generationSelectedIndexes = new Set();
  renderGenerateSourceList();
}

function renderGenerateCandidateCard(candidate, index) {
  const card = document.createElement("div");
  card.className = "generate-candidate";
  card.dataset.index = String(index);
  const bodyText = candidate.responseBody === undefined ? "" : JSON.stringify(candidate.responseBody, null, 2);
  const methodOptions = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    .map((method) => `<option${candidate.method === method ? " selected" : ""}>${method}</option>`)
    .join("");
  card.innerHTML = `
    <div class="generate-candidate-fields">
      <label>Method
        <select class="generate-candidate-method">${methodOptions}</select>
      </label>
      <label>Path
        <input type="text" class="generate-candidate-path" value="${escapeHtml(candidate.path || "")}" />
      </label>
      <label>Status code
        <input type="number" class="generate-candidate-status" value="${candidate.statusCode ?? 200}" min="100" max="599" />
      </label>
    </div>
    <label>Response body (JSON)
      <textarea class="generate-candidate-body" rows="4">${escapeHtml(bodyText)}</textarea>
    </label>
    <button type="button" class="generate-candidate-remove">Remove</button>
  `;
  card.querySelector(".generate-candidate-remove").addEventListener("click", () => {
    card.remove();
    generateApproveButton.disabled = generateCandidatesContainer.children.length === 0;
  });
  generateCandidatesContainer.appendChild(card);
}

function renderGenerateCandidates(candidates, rejected) {
  generationCandidates = candidates;
  generateCandidatesContainer.innerHTML = "";
  candidates.forEach((candidate, index) => renderGenerateCandidateCard(candidate, index));

  generateRejectedList.innerHTML = "";
  for (const item of rejected) {
    const li = document.createElement("li");
    li.textContent = `${item.reason} - ${JSON.stringify(item.raw)}`;
    generateRejectedList.appendChild(li);
  }
  generateRejectedSection.hidden = rejected.length === 0;

  generateResults.hidden = false;
  generateApproveButton.disabled = candidates.length === 0;
  generateLoadResult.hidden = true;
}

generateRunButton.addEventListener("click", async () => {
  clearGenerateError();
  generateResults.hidden = true;

  if (generationSelectedIndexes.size === 0) {
    showGenerateError("Select at least one captured request before generating.");
    return;
  }

  const mode = document.querySelector('input[name="generate-mode"]:checked').value;
  const sourceEntries = Array.from(generationSelectedIndexes)
    .sort((a, b) => a - b)
    .map((index) => generationSourceEntries[index]);

  generateRunButton.disabled = true;
  generateRunButton.textContent = "Generating…";
  try {
    const response = await fetch(withServer("/mock-ui/api/mock-generation/draft"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sourceEntries, mode }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || `generation failed: ${response.status}`);
    }
    const data = await response.json();
    renderGenerateCandidates(data.candidates, data.rejected);
  } catch (err) {
    showGenerateError(err.message);
  } finally {
    generateRunButton.disabled = generationSelectedIndexes.size === 0;
    generateRunButton.textContent = "Generate mocks with AI";
  }
});

generateApproveButton.addEventListener("click", async () => {
  clearGenerateError();

  const cards = generateCandidatesContainer.querySelectorAll(".generate-candidate");
  const mocksToLoad = [];
  for (const card of cards) {
    const index = Number(card.dataset.index);
    const original = generationCandidates[index] || {};
    const bodyText = card.querySelector(".generate-candidate-body").value.trim();
    let responseBody;
    try {
      responseBody = bodyText === "" ? {} : JSON.parse(bodyText);
    } catch (err) {
      showGenerateError(`Candidate ${index + 1}: response body must be valid JSON.`);
      return;
    }
    mocksToLoad.push({
      ...original,
      method: card.querySelector(".generate-candidate-method").value,
      path: card.querySelector(".generate-candidate-path").value,
      statusCode: Number(card.querySelector(".generate-candidate-status").value),
      responseBody,
    });
  }

  if (mocksToLoad.length === 0) {
    showGenerateError("No candidates left to load.");
    return;
  }

  generateApproveButton.disabled = true;
  try {
    const response = await fetch(withServer("/mock-ui/api/mock-generation/load"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mocks: mocksToLoad }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || `load failed: ${response.status}`);
    }
    const data = await response.json();

    generateCandidatesContainer.innerHTML = "";
    generateLoadResult.textContent =
      `Loaded ${data.loaded.length} mock${data.loaded.length === 1 ? "" : "s"} into MockServer.` +
      (data.rejected.length > 0 ? ` ${data.rejected.length} could not be loaded.` : "");
    generateLoadResult.hidden = false;
    for (const item of data.rejected) {
      const li = document.createElement("li");
      li.textContent = `${item.reason} - ${JSON.stringify(item.raw)}`;
      generateRejectedList.appendChild(li);
    }
    generateRejectedSection.hidden = generateRejectedList.children.length === 0;

    await loadMocks();
    showSuccessBanner(`Loaded ${data.loaded.length} AI-generated mock${data.loaded.length === 1 ? "" : "s"}.`);
  } catch (err) {
    showGenerateError(err.message);
  } finally {
    generateApproveButton.disabled = false;
  }
});

generateRefreshSourceButton.addEventListener("click", () => {
  loadGenerateSourceEntries().catch((err) => showGenerateError(err.message));
});

async function syncGeneratePage(page) {
  if (page !== "generate" || !generationAvailable) {
    return;
  }
  clearGenerateError();
  generateResults.hidden = true;
  try {
    await loadGenerateSourceEntries();
  } catch (err) {
    showGenerateError(err.message);
  }
}

async function init() {
  try {
    await loadServers();
  } catch (err) {
    showError(err.message);
  }
  await checkMockGenerationAvailability();
  const initialPage = getCurrentPageFromHash();
  showPage(initialPage);
  syncRequestsPageStream(initialPage);
  syncGeneratePage(initialPage);
  loadMocks().catch((err) => showError(err.message));
}

init();
