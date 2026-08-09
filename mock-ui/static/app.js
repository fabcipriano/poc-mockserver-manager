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
const requestsPauseToggle = document.getElementById("requests-pause-toggle");
const requestsError = document.getElementById("requests-error");

let requestsEventSource = null;
let requestsPaused = false;
let requestsPendingQueue = [];
let requestsFilterDebounce = null;

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

function requestsApiUrl(basePath) {
  const path = currentRequestsPathFilter();
  return path ? `${basePath}?path=${encodeURIComponent(path)}` : basePath;
}

function renderRequestRow(entry) {
  const row = document.createElement("tr");
  row.innerHTML = `
    <td>${entry.timestamp}</td>
    <td>${entry.method}</td>
    <td><code>${entry.path}</code></td>
    <td>${entry.statusCode}</td>
  `;
  return row;
}

function updateRequestsEmptyState() {
  requestsEmptyState.hidden = requestsBody.children.length > 0;
}

function prependRequestRow(entry) {
  requestsBody.insertBefore(renderRequestRow(entry), requestsBody.firstChild);
  updateRequestsEmptyState();
}

async function loadRequestHistory() {
  const response = await fetch(requestsApiUrl("/mock-ui/api/requests"));
  if (!response.ok) {
    throw new Error(`failed to load recent requests: ${response.status}`);
  }
  const entries = await response.json();
  requestsBody.innerHTML = "";
  for (const entry of entries) {
    requestsBody.appendChild(renderRequestRow(entry));
  }
  updateRequestsEmptyState();
}

function closeRequestsStream() {
  if (requestsEventSource) {
    requestsEventSource.close();
    requestsEventSource = null;
  }
}

function openRequestsStream() {
  closeRequestsStream();
  requestsEventSource = new EventSource(requestsApiUrl("/mock-ui/api/requests/stream"));
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

requestsPathFilter.addEventListener("input", () => {
  if (requestsFilterDebounce) {
    clearTimeout(requestsFilterDebounce);
  }
  requestsFilterDebounce = setTimeout(() => {
    clearRequestsError();
    requestsPendingQueue = [];
    loadRequestHistory().catch((err) => showRequestsError(err.message));
    openRequestsStream();
  }, 300);
});

const initialPage = getCurrentPageFromHash();
showPage(initialPage);
syncRequestsPageStream(initialPage);
loadMocks().catch((err) => showError(err.message));
