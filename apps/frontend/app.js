const state = {
  data: null,
  charts: {},
  filters: {
    region: "all",
    service: "all"
  }
};

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

const fmt = (value) => currency.format(value);

async function fetchJson(path, options) {
  const response = await fetch(path, options);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
}

async function renderSetupBanner() {
  const banner = document.querySelector("#setupBanner");
  const setup = await fetchJson("/api/setup");

  if (setup.ready && setup.dataProvider !== "oci") {
    banner.hidden = true;
    return;
  }

  if (setup.ready) {
    banner.className = "setup-banner ok";
    banner.innerHTML = `<strong>OCI live mode is configured.</strong><span> Container limits: ${setup.docker.memoryLimit} memory, ${setup.docker.cpuLimit} CPU.</span>`;
    banner.hidden = false;
    return;
  }

  const missing = setup.missing.map((item) => `<li><strong>${item.label}:</strong> ${item.help}</li>`).join("");
  banner.className = "setup-banner warn";
  banner.innerHTML = `
    <strong>OCI setup needs attention.</strong>
    <span>The app is running, but live OCI data needs these items:</span>
    <ul>${missing}</ul>
  `;
  banner.hidden = false;
}

function queryString() {
  const params = new URLSearchParams();
  params.set("region", state.filters.region);
  params.set("service", state.filters.service);
  return params.toString();
}

function setSelectOptions(select, values, allLabel) {
  const current = select.value || "all";
  select.innerHTML = [`<option value="all">${allLabel}</option>`, ...values.map((value) => `<option value="${value}">${value}</option>`)].join("");
  select.value = values.includes(current) ? current : "all";
}

function renderHeader(data) {
  document.querySelector("#tenancy").textContent = data.meta.tenancy;
  document.querySelector("#period").textContent = data.meta.period;
  document.querySelector("#mode").textContent = `${data.meta.mode} mode`;
  setSelectOptions(document.querySelector("#region"), data.meta.regions, "All regions");
  setSelectOptions(document.querySelector("#service"), data.meta.services, "All services");
}

function renderKpis(summary) {
  const savingsPercent = summary.currentRunRate > 0 ? `${Math.round((summary.identifiedSavings / summary.currentRunRate) * 100)}% of spend` : "cost data unavailable";
  const cards = [
    ["Current run rate", fmt(summary.currentRunRate), `up ${summary.monthOverMonthPercent.toFixed(1)}% MoM`, "up"],
    ["Projected next month", fmt(summary.projectedNextMonth), "forecast", ""],
    ["Identified savings", fmt(summary.identifiedSavings), savingsPercent, "down"],
    ["Optimized run rate", fmt(summary.optimizedRunRate), "if all open items apply", "down"],
    ["Open recommendations", summary.openRecommendations, `${summary.highImpactRecommendations} high impact`, ""]
  ];

  document.querySelector("#kpis").innerHTML = cards
    .map(([label, value, delta, className]) => `
      <div class="kpi-card">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
        <div class="delta ${className}">${delta}</div>
      </div>
    `)
    .join("");
}

function destroyChart(name) {
  if (state.charts[name]) {
    state.charts[name].destroy();
  }
}

function renderTrend(data) {
  destroyChart("trend");
  const actualLabels = data.dailyCosts.map((point) => point.date.slice(5));
  const forecastLabels = data.forecast.map((point) => point.date.slice(5));
  const actualValues = data.dailyCosts.map((point) => Math.round(point.cost));
  const forecastValues = data.forecast.length
    ? Array(Math.max(data.dailyCosts.length - 1, 0)).fill(null).concat([
        actualValues.at(-1) ?? 0,
        ...data.forecast.map((point) => Math.round(point.cost))
      ])
    : [];

  state.charts.trend = new Chart(document.querySelector("#trendChart"), {
    type: "line",
    data: {
      labels: actualLabels.concat(forecastLabels),
      datasets: [
        {
          label: "Actual",
          data: actualValues,
          borderColor: "#ff7a35",
          backgroundColor: "rgba(255, 122, 53, 0.12)",
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.35
        },
        {
          label: "Forecast",
          data: forecastValues,
          borderColor: "#5b94ff",
          borderDash: [5, 4],
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.35
        }
      ]
    },
    options: chartOptions()
  });
}

function renderServiceChart(data) {
  destroyChart("service");
  const labels = data.meta.services;
  const values = labels.map((label) => Math.round(data.spendByService[label] ?? 0));
  const chartValues = values.some((value) => value > 0) ? values : labels.map(() => 1);

  state.charts.service = new Chart(document.querySelector("#serviceChart"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: chartValues,
          backgroundColor: ["#ff7a35", "#5b94ff", "#35c486", "#f4b23f"],
          borderColor: "#121826",
          borderWidth: 2
        }
      ]
    },
    options: {
      cutout: "62%",
      plugins: {
        legend: {
          position: "right",
          labels: {
            color: "#cbd8ea",
            boxWidth: 12,
            padding: 10
          }
        }
      }
    }
  });
}

function renderCompartmentChart(data) {
  destroyChart("compartment");
  const labels = data.meta.compartments;
  const values = labels.map((label) => Math.round(data.spendByCompartment[label] ?? 0));
  const chartValues = values.some((value) => value > 0) ? values : labels.map(() => 1);

  state.charts.compartment = new Chart(document.querySelector("#compartmentChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          data: chartValues,
          backgroundColor: "#5b94ff",
          borderRadius: 5
        }
      ]
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: "#6f7f96", callback: (value) => `$${value}` },
          grid: { color: "#1b2639" }
        },
        y: {
          ticks: { color: "#cbd8ea" },
          grid: { display: false }
        }
      }
    }
  });
}

function chartOptions() {
  return {
    plugins: {
      legend: {
        labels: {
          color: "#93a1b6",
          boxWidth: 12
        }
      }
    },
    scales: {
      x: {
        ticks: {
          color: "#6f7f96",
          maxTicksLimit: 9
        },
        grid: { display: false }
      },
      y: {
        ticks: {
          color: "#6f7f96",
          callback: (value) => `$${value}`
        },
        grid: { color: "#1b2639" }
      }
    }
  };
}

function severityLabel(severity) {
  return severity === "medium" ? "Medium" : severity === "high" ? "High" : "Low";
}

function renderRecommendations(data) {
  const recommendations = data.recommendations.slice(0, 8);
  document.querySelector("#recommendationHint").textContent = `${data.recommendations.length} findings · ${fmt(data.summary.identifiedSavings)}/mo potential`;
  document.querySelector("#recommendations").innerHTML = recommendations
    .map((rec) => `
      <article class="rec">
        <div class="rec-top">
          <span class="badge ${rec.severity}">${severityLabel(rec.severity)}</span>
          <span class="service-pill">${rec.service}</span>
        </div>
        <h3>${rec.title}</h3>
        <p>${rec.evidence}</p>
        <div class="rec-action">${rec.summary} ${rec.action}</div>
        <div class="rec-save">Est. savings ${fmt(rec.estimatedMonthlySavings)}/mo · confidence ${Math.round(rec.confidence * 100)}%</div>
      </article>
    `)
    .join("");
}

function renderResources(data) {
  const flagged = new Set(data.recommendations.map((rec) => rec.resourceId).filter(Boolean));
  const color = (utilization) => {
    if (utilization < 20) return "#ff6262";
    if (utilization < 50) return "#f4b23f";
    return "#35c486";
  };

  document.querySelector("#resources").innerHTML = data.resources
    .slice(0, 40)
    .map((resource) => `
      <tr>
        <td class="resource-name">${flagged.has(resource.id) ? "Flag " : ""}${resource.name}</td>
        <td>${resource.service}</td>
        <td>${resource.region}</td>
        <td>${resource.shape}</td>
        <td><span class="util"><i style="width: ${resource.utilization}%; background: ${color(resource.utilization)}"></i></span> ${resource.utilization}%</td>
        <td class="num">${fmt(resource.monthlyCost)}</td>
      </tr>
    `)
    .join("");
}

function renderAll(data) {
  state.data = data;
  renderHeader(data);
  renderKpis(data.summary);
  renderTrend(data);
  renderServiceChart(data);
  renderRecommendations(data);
  renderCompartmentChart(data);
  renderResources(data);
}

async function loadDashboard() {
  const data = await fetchJson(`/api/dashboard?${queryString()}`);
  renderAll(data);
}

function pushMessage(text, who) {
  const chat = document.querySelector("#chat");
  const message = document.createElement("div");
  message.className = `msg ${who}`;
  message.textContent = text;
  chat.appendChild(message);
  chat.scrollTop = chat.scrollHeight;
}

async function askCopilot(question) {
  pushMessage(question, "user");
  const input = document.querySelector("#question");
  input.value = "";
  const answer = await fetchJson("/api/copilot", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, filters: state.filters })
  });
  pushMessage(answer.answer, "bot");
}

function exportCsv() {
  const rows = [
    ["Title", "Severity", "Service", "Owner", "Monthly Savings", "Annual Savings"],
    ...state.data.recommendations.map((rec) => [
      rec.title,
      rec.severity,
      rec.service,
      rec.owner,
      Math.round(rec.estimatedMonthlySavings),
      Math.round(rec.estimatedAnnualSavings)
    ])
  ];
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
  const link = document.createElement("a");
  link.href = `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
  link.download = "oci-cost-optimizer-mock-recommendations.csv";
  link.click();
}

function wireEvents() {
  document.querySelector("#filters").addEventListener("change", async (event) => {
    if (event.target.id === "region" || event.target.id === "service") {
      state.filters[event.target.id] = event.target.value;
      await loadDashboard();
    }
  });

  document.querySelector("#copilotForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = document.querySelector("#question").value.trim();
    if (question) {
      await askCopilot(question);
    }
  });

  document.querySelector("#export").addEventListener("click", exportCsv);

  const suggestions = ["Where can I save the most?", "Forecast next month", "Spend by region", "What's wrong with compute?"];
  document.querySelector("#suggestions").innerHTML = suggestions.map((item) => `<button type="button">${item}</button>`).join("");
  document.querySelectorAll("#suggestions button").forEach((button) => {
    button.addEventListener("click", () => askCopilot(button.textContent));
  });
}

wireEvents();
renderSetupBanner()
  .catch(() => {})
  .then(loadDashboard)
  .then(() => {
    pushMessage(`I loaded the ${state.data.meta.mode} OCI tenancy. Current run rate is ${fmt(state.data.summary.currentRunRate)}/mo with ${fmt(state.data.summary.identifiedSavings)}/mo in identified savings.`, "bot");
  })
  .catch((error) => {
    document.body.innerHTML = `<main class="shell"><section class="panel"><h1>Mock failed to load</h1><p>${error.message}</p></section></main>`;
  });
