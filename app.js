// Blinkdrop frontend wiring. Vanilla, no build step.
// Both pages degrade to working HTML if this file never loads.

const STATUS_LABELS = {
  pending: "Pending",
  needs_review: "Needs review",
  approved: "Approved",
  waived: "Waived",
  exported: "Exported",
};

function money(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

function clockTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

function initForm(form) {
  const error = document.getElementById("form-error");
  const submit = document.getElementById("btn-submit-feedback");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    submit.disabled = true;

    const data = new FormData(form);
    const rating = data.get("rating");
    try {
      await fetchJSON("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_ref: data.get("job_ref") || "",
          rating: rating ? Number(rating) : null,
          comment: data.get("comment") || "",
          late: data.get("late") !== null,
          damaged: data.get("damaged") !== null,
        }),
      });
      location.assign("thanks.html");
    } catch {
      error.hidden = false;
      submit.disabled = false;
    }
  });
}

function renderStats(stats) {
  const set = (id, value, caption) => {
    const card = document.getElementById(id);
    card.querySelector(".stat-card-value").textContent = value;
    if (caption !== undefined) card.querySelector(".stat-card-caption").textContent = caption;
  };

  set("stat-exceptions-today", String(stats.exceptions_today), "filed so far");
  set("stat-pending-review", String(stats.pending_review), "awaiting action");
  set(
    "stat-approved-today",
    money(stats.approved_today_cents),
    `${stats.approved_today_count} charge${stats.approved_today_count === 1 ? "" : "s"}`,
  );
  set(
    "stat-top-driver",
    stats.top_driver ? stats.top_driver.driver : "—",
    stats.top_driver ? `${stats.top_driver.count} today` : "no data yet",
  );

  const list = document.getElementById("list-by-driver");
  const empty = document.getElementById("empty-by-driver");
  list.textContent = "";
  if (!stats.by_driver.length) {
    list.hidden = true;
    empty.hidden = false;
    return;
  }
  for (const row of stats.by_driver) {
    const item = document.createElement("li");
    item.textContent = `${row.driver} — ${row.count}`;
    list.appendChild(item);
  }
  list.hidden = false;
  empty.hidden = true;
}

function renderRows(items) {
  const body = document.getElementById("tbody-exceptions");
  body.textContent = "";

  if (!items.length) {
    const row = document.createElement("tr");
    row.className = "table-empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.textContent = "No exceptions match this filter.";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  for (const item of items) {
    const row = document.createElement("tr");

    const selectCell = document.createElement("td");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.className = "row-select";
    box.dataset.id = item.id;
    box.setAttribute("aria-label", `Select ${item.job_ref}`);
    selectCell.appendChild(box);
    row.appendChild(selectCell);

    // textContent throughout: the comment field is free text from the public form.
    const cells = [
      item.driver,
      item.customer,
      item.job_ref,
      item.type_label,
      clockTime(item.created_at),
      money(item.charge_cents),
    ];
    for (const value of cells) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    }

    const statusCell = document.createElement("td");
    statusCell.textContent = STATUS_LABELS[item.status] || item.status;
    statusCell.className =
      item.status === "approved" ? "status-cell status-cell--approved" : "status-cell";
    row.appendChild(statusCell);

    body.appendChild(row);
  }
}

async function loadDashboard(status) {
  const [stats, exceptions] = await Promise.all([
    fetchJSON("/api/stats"),
    fetchJSON(`/api/exceptions?status=${encodeURIComponent(status)}`),
  ]);
  renderStats(stats);
  renderRows(exceptions.items);
}

function initDashboard() {
  const pills = [...document.querySelectorAll(".pill-tab")];

  for (const pill of pills) {
    pill.addEventListener("click", () => {
      for (const other of pills) {
        const active = other === pill;
        other.classList.toggle("is-active", active);
        other.setAttribute("aria-selected", String(active));
      }
      loadDashboard(pill.dataset.status);
    });
  }

  const selectAll = document.getElementById("input-select-all");
  selectAll.addEventListener("change", () => {
    for (const box of document.querySelectorAll(".row-select")) box.checked = selectAll.checked;
  });

  loadDashboard("all");
}

const feedbackForm = document.getElementById("form-feedback");
if (feedbackForm) initForm(feedbackForm);
if (document.getElementById("table-exceptions")) initDashboard();
