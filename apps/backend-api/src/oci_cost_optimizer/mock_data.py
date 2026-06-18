from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import math
import re
from typing import Any


REGIONS = ["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1", "ap-mumbai-1"]
COMPARTMENTS = ["prod-app", "data-platform", "analytics", "dev-sandbox", "shared-network"]
SERVICES = ["Compute", "Storage", "Database", "Networking"]

SHAPES = {
    "Compute": ["VM.Standard.E4.Flex", "VM.Standard3.Flex", "VM.Optimized3.Flex", "BM.Standard.E4.128", "VM.Standard.A1.Flex"],
    "Storage": ["Block Volume", "Object Storage", "Boot Volume", "File Storage", "Archive Storage"],
    "Database": ["Autonomous DB (ATP)", "Autonomous DB (ADW)", "Base DB VM.Standard2", "Exadata DB", "MySQL HeatWave"],
    "Networking": ["Flexible Load Balancer", "NAT Gateway", "Data Egress", "Reserved Public IP", "FastConnect"],
}


@dataclass(frozen=True)
class Resource:
    id: str
    name: str
    service: str
    shape: str
    region: str
    compartment: str
    monthlyCost: float
    utilization: int
    status: str
    attached: bool
    provisioned: dict[str, Any] | None


def money(value: float) -> float:
    return round(value + 1e-9, 2)


class DeterministicRandom:
    def __init__(self, seed: int) -> None:
        self.seed = seed

    def next(self) -> float:
        self.seed = (self.seed * 1103515245 + 12345) & 0x7FFFFFFF
        return self.seed / 0x7FFFFFFF


def _create_resources(random: DeterministicRandom) -> list[Resource]:
    resources: list[Resource] = []
    next_id = 1

    def add(service: str, count: int) -> None:
        nonlocal next_id

        for _ in range(count):
            shape = SHAPES[service][math.floor(random.next() * len(SHAPES[service]))]
            region = REGIONS[math.floor(random.next() * len(REGIONS))]
            compartment = COMPARTMENTS[math.floor(random.next() * len(COMPARTMENTS))]
            attached = True
            provisioned = None

            if service == "Compute":
                monthly_cost = 120 + random.next() * 2400
                utilization = round(random.next() * 100)
            elif service == "Storage":
                monthly_cost = 15 + random.next() * 900
                utilization = round(random.next() * 100)
                attached = random.next() > 0.22
            elif service == "Database":
                monthly_cost = 300 + random.next() * 5200
                utilization = round(random.next() * 100)
                provisioned = {"ocpu": math.ceil(2 + random.next() * 30)}
            else:
                monthly_cost = 20 + random.next() * 1600
                utilization = round(random.next() * 100)

            resources.append(
                Resource(
                    id=f"ocid1.{service.lower()}.{next_id:04d}",
                    name=f"{service[:3].lower()}-{compartment.split('-')[0]}-{100 + math.floor(random.next() * 899)}",
                    service=service,
                    shape=shape,
                    region=region,
                    compartment=compartment,
                    monthlyCost=money(monthly_cost),
                    utilization=utilization,
                    status="running",
                    attached=attached,
                    provisioned=provisioned,
                )
            )
            next_id += 1

    add("Compute", 26)
    add("Storage", 22)
    add("Database", 9)
    add("Networking", 14)
    return resources


def _create_daily_costs(resources: list[Resource], random: DeterministicRandom) -> list[dict[str, Any]]:
    monthly_run_rate = sum(resource.monthlyCost for resource in resources)
    today = date(2026, 6, 17)
    daily_costs: list[dict[str, Any]] = []

    for offset in range(29, -1, -1):
        day = today - timedelta(days=offset)
        weekend_factor = 0.82 if day.weekday() in {5, 6} else 1
        drift_factor = 1 + (30 - offset) * 0.004
        noise_factor = 0.92 + random.next() * 0.16

        daily_costs.append(
            {
                "date": day.isoformat(),
                "cost": money((monthly_run_rate / 30) * weekend_factor * drift_factor * noise_factor),
                "type": "actual",
            }
        )

    return daily_costs


def _forecast_daily_costs(daily_costs: list[dict[str, Any]], days: int = 14) -> list[dict[str, Any]]:
    recent = daily_costs[-14:]
    xs = list(range(len(recent)))
    ys = [point["cost"] for point in recent]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (ys[index] - mean_y) for index, x in enumerate(xs))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    last_date = date.fromisoformat(daily_costs[-1]["date"])

    return [
        {
            "date": (last_date + timedelta(days=index + 1)).isoformat(),
            "cost": money(intercept + slope * (len(recent) + index)),
            "type": "forecast",
        }
        for index in range(days)
    ]


def _recommendation_id(service: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:42]
    return f"rec-{service.lower()}-{slug}"


def _make_recommendation(
    *,
    severity: str,
    service: str,
    resource: Resource | None,
    savings: float,
    title: str,
    evidence: str,
    summary: str,
    action: str,
    risk: str = "low",
    confidence: float = 0.82,
) -> dict[str, Any]:
    return {
        "id": _recommendation_id(service, title),
        "severity": severity,
        "service": service,
        "resourceId": resource.id if resource else None,
        "resourceName": resource.name if resource else "Account baseline",
        "title": title,
        "evidence": evidence,
        "summary": summary,
        "action": action,
        "estimatedMonthlySavings": money(savings),
        "estimatedAnnualSavings": money(savings * 12),
        "confidence": confidence,
        "risk": risk,
        "owner": resource.compartment if resource else "finops",
        "status": "open",
    }


def _create_recommendations(resources: list[Resource]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    for resource in resources:
        if resource.service == "Compute" and resource.utilization < 15:
            recommendations.append(
                _make_recommendation(
                    severity="high",
                    service="Compute",
                    resource=resource,
                    savings=resource.monthlyCost * 0.95,
                    title=f"Idle instance: {resource.name}",
                    evidence=f"{resource.shape} in {resource.region} averaged {resource.utilization}% CPU over 30 days.",
                    summary="This VM appears idle and can likely be stopped on a schedule or retired after owner confirmation.",
                    action="Confirm no batch dependency, snapshot if needed, then stop nightly or terminate.",
                )
            )
        elif resource.service == "Compute" and resource.utilization < 40:
            recommendations.append(
                _make_recommendation(
                    severity="medium",
                    service="Compute",
                    resource=resource,
                    savings=resource.monthlyCost * 0.45,
                    title=f"Oversized shape: {resource.name}",
                    evidence=f"{resource.shape} is running at {resource.utilization}% utilization.",
                    summary="Flex shape capacity is above observed demand and should be reduced after checking p95 utilization.",
                    action="Reduce OCPU and memory by roughly half, then monitor for one business cycle.",
                    confidence=0.76,
                )
            )

        if resource.service == "Storage" and not resource.attached:
            recommendations.append(
                _make_recommendation(
                    severity="high",
                    service="Storage",
                    resource=resource,
                    savings=resource.monthlyCost,
                    title=f"Unattached volume: {resource.name}",
                    evidence=f"{resource.shape} in {resource.region} has no active attachment.",
                    summary="Orphaned storage is billing at full rate without serving a workload.",
                    action="Snapshot for retention, move cold backup to Object Storage, then delete the volume.",
                )
            )
        elif resource.service == "Storage" and resource.shape == "Block Volume" and resource.utilization < 30:
            recommendations.append(
                _make_recommendation(
                    severity="low",
                    service="Storage",
                    resource=resource,
                    savings=resource.monthlyCost * 0.3,
                    title=f"Over-provisioned volume: {resource.name}",
                    evidence=f"Only {resource.utilization}% of provisioned block volume capacity is used.",
                    summary="The provisioned volume has room to shrink or move to a cheaper performance tier.",
                    action="Lower the performance tier or resize after confirming free-space trend.",
                )
            )

        if resource.service == "Database" and resource.utilization < 35:
            is_autonomous = "Autonomous" in resource.shape
            recommendations.append(
                _make_recommendation(
                    severity="medium",
                    service="Database",
                    resource=resource,
                    savings=resource.monthlyCost * (0.4 if is_autonomous else 0.35),
                    title=f"{'Tune autonomous baseline' if is_autonomous else 'Right-size database'}: {resource.name}",
                    evidence=f"{resource.shape} is averaging {resource.utilization}% utilization.",
                    summary="Database capacity is provisioned above observed baseline demand.",
                    action="Lower baseline OCPU, enable autoscaling where available, and review off-peak schedules.",
                    risk="medium",
                    confidence=0.72,
                )
            )

        if resource.service == "Networking" and resource.shape == "Flexible Load Balancer" and resource.utilization < 20:
            recommendations.append(
                _make_recommendation(
                    severity="low",
                    service="Networking",
                    resource=resource,
                    savings=resource.monthlyCost * 0.6,
                    title=f"Idle load balancer: {resource.name}",
                    evidence=f"Load balancer bandwidth utilization is {resource.utilization}%.",
                    summary="Reserved load balancer bandwidth is above current traffic needs.",
                    action="Reduce minimum bandwidth or consolidate routes onto a shared load balancer.",
                )
            )
        elif resource.service == "Networking" and resource.shape == "Data Egress" and resource.monthlyCost > 800:
            recommendations.append(
                _make_recommendation(
                    severity="medium",
                    service="Networking",
                    resource=resource,
                    savings=resource.monthlyCost * 0.25,
                    title=f"High egress cost: {resource.name}",
                    evidence=f"Monthly egress cost is ${round(resource.monthlyCost):,}.",
                    summary="Cross-region or internet egress is large enough to justify architectural review.",
                    action="Co-locate chatty services, add CDN for static assets, and prefer private endpoints.",
                    risk="medium",
                )
            )
        elif resource.service == "Networking" and resource.shape == "Reserved Public IP" and resource.utilization < 5:
            recommendations.append(
                _make_recommendation(
                    severity="low",
                    service="Networking",
                    resource=resource,
                    savings=resource.monthlyCost,
                    title=f"Unused reserved IP: {resource.name}",
                    evidence="Reserved public IP is not bound to active traffic.",
                    summary="Reserved IPs continue to bill while unattached.",
                    action="Release the reserved IP after owner confirmation.",
                )
            )

    steady_compute_spend = sum(resource.monthlyCost for resource in resources if resource.service == "Compute")

    if steady_compute_spend > 4000:
        recommendations.append(
            _make_recommendation(
                severity="high",
                service="Compute",
                resource=None,
                savings=steady_compute_spend * 0.28,
                title="Adopt a Universal Credits commitment",
                evidence=f"${round(steady_compute_spend):,} per month of steady on-demand compute spend.",
                summary="The baseline compute footprint is large enough for a commitment discount scenario.",
                action="Commit only the steady baseline and keep burst workloads on demand.",
                risk="medium",
                confidence=0.69,
            )
        )

    return sorted(recommendations, key=lambda item: item["estimatedMonthlySavings"], reverse=True)


def _aggregate(resources: list[Resource], field_name: str) -> dict[str, float]:
    groups: dict[str, float] = {}

    for resource in resources:
        key = getattr(resource, field_name)
        groups[key] = money(groups.get(key, 0) + resource.monthlyCost)

    return groups


def _filter_resources(resources: list[Resource], filters: dict[str, str] | None = None) -> list[Resource]:
    filters = filters or {}
    service = filters.get("service", "all")
    region = filters.get("region", "all")

    return [
        resource
        for resource in resources
        if (service == "all" or resource.service == service) and (region == "all" or resource.region == region)
    ]


def create_mock_cost_optimizer_data(filters: dict[str, str] | None = None) -> dict[str, Any]:
    filters = filters or {}
    random = DeterministicRandom(424242)
    all_resources = _create_resources(random)
    daily_costs = _create_daily_costs(all_resources, random)
    forecast = _forecast_daily_costs(daily_costs)
    resources = sorted(_filter_resources(all_resources, filters), key=lambda resource: resource.monthlyCost, reverse=True)
    recommendations = _create_recommendations(resources)
    current_run_rate = money(sum(resource.monthlyCost for resource in resources))
    identified_savings = money(sum(recommendation["estimatedMonthlySavings"] for recommendation in recommendations))

    return {
        "meta": {
            "mode": "mock",
            "tenancy": "acme-prod",
            "period": "last 30 days",
            "generatedAt": "2026-06-17T00:00:00.000Z",
            "regions": REGIONS,
            "services": SERVICES,
            "compartments": COMPARTMENTS,
            "filters": {
                "service": filters.get("service", "all"),
                "region": filters.get("region", "all"),
            },
        },
        "summary": {
            "currentRunRate": current_run_rate,
            "projectedNextMonth": money(current_run_rate * 1.04),
            "identifiedSavings": identified_savings,
            "optimizedRunRate": money(current_run_rate - identified_savings),
            "openRecommendations": len(recommendations),
            "highImpactRecommendations": len([item for item in recommendations if item["severity"] == "high"]),
            "monthOverMonthPercent": 6.1,
        },
        "dailyCosts": daily_costs,
        "forecast": forecast,
        "spendByService": _aggregate(resources, "service"),
        "spendByCompartment": _aggregate(resources, "compartment"),
        "resources": [asdict(resource) for resource in resources],
        "recommendations": recommendations,
    }


def answer_mock_copilot(question: str, filters: dict[str, str] | None = None) -> str:
    data = create_mock_cost_optimizer_data(filters)
    query = question.lower()

    def fmt(value: float) -> str:
        return f"${round(value):,}"

    def service_spend(service: str) -> float:
        return data["spendByService"].get(service, 0)

    if re.search(r"save|saving|reduce|cut|lower", query):
        top = [
            f"{index + 1}. {recommendation['title']} -> {fmt(recommendation['estimatedMonthlySavings'])}/mo"
            for index, recommendation in enumerate(data["recommendations"][:3])
        ]
        percent = round((data["summary"]["identifiedSavings"] / data["summary"]["currentRunRate"]) * 100)
        return f"Potential savings are {fmt(data['summary']['identifiedSavings'])}/mo, about {percent}% of current spend.\n\nBiggest wins:\n" + "\n".join(top)

    if re.search(r"forecast|next month|project|predict", query):
        return (
            f"Current run rate is {fmt(data['summary']['currentRunRate'])}/mo. "
            f"The mock forecast projects {fmt(data['summary']['projectedNextMonth'])}/mo next month, "
            f"or {fmt(data['summary']['optimizedRunRate'])}/mo if every open recommendation is applied."
        )

    if re.search(r"compute|vm|instance|cpu", query):
        idle = len([resource for resource in data["resources"] if resource["service"] == "Compute" and resource["utilization"] < 15])
        return f"Compute is {fmt(service_spend('Compute'))}/mo. I found {idle} idle instance(s) below 15% utilization plus several flex shapes that look oversized."

    if re.search(r"storage|volume|disk|bucket", query):
        orphaned = len([resource for resource in data["resources"] if resource["service"] == "Storage" and not resource["attached"]])
        return f"Storage is {fmt(service_spend('Storage'))}/mo. {orphaned} unattached volume(s) are candidates for snapshot-and-delete cleanup."

    if re.search(r"database|db|autonomous|exadata", query):
        return f"Database is {fmt(service_spend('Database'))}/mo. The main levers are lower baselines, autoscaling, scheduled scale-down, and BYOL review."

    if re.search(r"network|egress|load balancer|bandwidth", query):
        return f"Networking is {fmt(service_spend('Networking'))}/mo. High egress and low-traffic load balancers are the mock findings to review first."

    if "region" in query:
        regions = sorted(_aggregate([Resource(**resource) for resource in data["resources"]], "region").items(), key=lambda item: item[1], reverse=True)
        return "\n".join(f"{region}: {fmt(spend)}/mo" for region, spend in regions)

    return (
        f"Run rate is {fmt(data['summary']['currentRunRate'])}/mo across {len(data['resources'])} resources, "
        f"with {fmt(data['summary']['identifiedSavings'])}/mo in open savings recommendations."
    )
