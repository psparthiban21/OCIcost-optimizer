# Dashboard Template Direction

The first frontend prototype should follow the reference HTML stored at:

```text
prototypes/oci-cost-optimizer.html
```

## Visual Direction

- Dark operational dashboard.
- Compact FinOps layout with dense, scannable information.
- Oracle-inspired red/orange accent for primary actions.
- Blue, green, amber, and red status colors for charts, savings, warning, and risk states.
- Cards for KPIs, chart panels, recommendation items, chat messages, and resource rows.
- Responsive layout that moves from multi-column desktop to single-column mobile.

## First Screen Content

The dashboard should open directly into the working cost optimizer experience, not a marketing page.

Required first-screen elements:

- Header with product name, tenancy, period, region filter, service filter, and export action.
- KPI row:
  - Current run rate.
  - Projected next month.
  - Identified savings.
  - Optimized run rate.
  - Open recommendations.
- Daily spend and forecast chart.
- Spend by service chart.
- AI savings recommendations.
- Cost Copilot chat.
- Spend by compartment.
- Top resources by cost.

## Prototype Behavior

The reference prototype currently uses:

- Explicit mock demo mode through `APP_CONFIG.mode = "mock"`.
- Client-side deterministic mock OCI data.
- Client-side rule-based recommendation detection.
- Client-side Cost Copilot responses.
- Chart.js charts loaded from CDN.
- CSV export generated in the browser.

This is useful for demonstration, but these pieces should become real application services during implementation.

## Mock Mode Requirement

Keep `prototypes/oci-cost-optimizer.html` working as a standalone mock dashboard even after the Minikube application is built.

This file is the backup demo path when:

- Minikube fails to start.
- Backend services are unavailable.
- OCI credentials are not configured.
- The LLM endpoint is unavailable.
- Network access to the local cluster is blocked.

Future work should add live API mode beside mock mode, not replace mock mode. The HTML prototype should continue to render KPI cards, charts, recommendations, top resources, Cost Copilot responses, and CSV export from deterministic in-browser data.

## Production Mapping

| Prototype Area | Production Service |
| --- | --- |
| Mock resource array | Ingestion service plus state database |
| Client recommendation rules | Cost analytics engine |
| Client AI explanation text | Recommendation orchestrator plus AI agents |
| `askCopilot()` | Backend API endpoint backed by LLM provider adapter |
| Client-side filters | Backend query parameters plus cache |
| Browser CSV export | Backend export endpoint or frontend export from API data |
| Chart.js direct data | API-driven chart datasets |

## Frontend Implementation Notes

- Keep the same information architecture and visual rhythm.
- Replace generated mock data with API responses.
- Keep filter state shareable through URL query parameters.
- Keep recommendation cards structured so they can show severity, category, evidence, savings, confidence, and lifecycle status.
- Add loading, empty, error, and stale-data states.
- Add role-aware controls for approval, rejection, assignment, and remediation planning.
- Keep the Cost Copilot visible beside recommendations on desktop and below recommendations on mobile.

## API Data Needed by the Dashboard

The first frontend implementation needs these API responses:

- Cost summary KPIs.
- Daily cost actuals and forecast.
- Spend by service.
- Spend by compartment.
- Top resources by cost.
- Recommendation list.
- Recommendation detail.
- Copilot answer.
- Export report.
