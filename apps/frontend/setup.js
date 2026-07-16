const API_BASE = "/api/v1";

async function fetchJson(path, options) {
  const response = await fetch(path, options);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.message || payload.error || `Request failed: ${response.status}`);
  }

  return payload;
}

function renderChecks(setup) {
  const checks = document.querySelector("#setupChecks");
  checks.innerHTML = `
    <h2>Configuration checks</h2>
    <ul>
      ${setup.checks
        .map((item) => `
          <li class="${item.ok ? "ok" : "warn"}">
            <span>${item.ok ? "OK" : "Missing"}</span>
            <strong>${item.label}</strong>
            <em>${item.value}</em>
            <p>${item.help}</p>
          </li>
        `)
        .join("")}
    </ul>
  `;
}

function showResult(message, className) {
  const result = document.querySelector("#setupResult");
  result.className = `setup-result ${className}`;
  result.textContent = message;
  result.hidden = false;
}

async function loadSetup() {
  const setup = await fetchJson(`${API_BASE}/setup`);
  renderChecks(setup);

  if (setup.envFile?.path) {
    document.querySelector("#envFilePath").value = setup.envFile.path;
  }
}

document.querySelector("#envFileForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const path = document.querySelector("#envFilePath").value.trim();

  try {
    const payload = await fetchJson(`${API_BASE}/setup/env-file`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path })
    });
    showResult(`Loaded ${payload.envFile}`, "ok");
    renderChecks(payload.setup);
  } catch (error) {
    showResult(error.message, "warn");
  }
});

loadSetup().catch((error) => showResult(error.message, "warn"));
