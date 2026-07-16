from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import json
import os
import subprocess
from typing import Any

from .config import Settings
from .mock_data import Resource, _forecast_daily_costs, money


class OciDataError(RuntimeError):
    pass


SERVICE_BY_RESOURCE_TYPE = {
    "Instance": "Compute",
    "BootVolume": "Storage",
    "Volume": "Storage",
    "Bucket": "Storage",
    "FileSystem": "Storage",
    "AutonomousDatabase": "Database",
    "Database": "Database",
    "DbSystem": "Database",
    "LoadBalancer": "Networking",
    "NatGateway": "Networking",
    "Drg": "Networking",
    "Vcn": "Networking",
    "Subnet": "Networking",
    "PublicIp": "Networking",
}


def _run_oci(settings: Settings, args: list[str], timeout: int = 25) -> dict[str, Any]:
    if not settings.oci_tenancy_ocid:
        raise OciDataError("OCI_TENANCY_OCID is missing")

    command = [
        str(settings.oci_cli_path),
        *args,
        "--config-file",
        str(settings.oci_config_file),
        "--profile",
        settings.oci_profile,
        "--auth",
        "api_key",
    ]

    try:
        env = {
            **os.environ,
            "OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING": "True",
            "OCI_CLI_SUPPRESS_UPDATE_CHECK": "True",
        }
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout, env=env)
    except FileNotFoundError as exc:
        raise OciDataError(f"OCI CLI was not found at {settings.oci_cli_path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise OciDataError("OCI CLI request timed out") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip().splitlines()
        if not message and completed.returncode < 0:
            raise OciDataError(f"OCI CLI was terminated by signal {-completed.returncode}")
        if not message:
            raise OciDataError(f"OCI CLI exited with status {completed.returncode}")
        raise OciDataError(message[-1] if message else "OCI CLI request failed")

    try:
        output = completed.stdout.strip()
        if not output:
            return {"data": []}
        json_start = min([index for index in (output.find("{"), output.find("[")) if index >= 0], default=-1)
        if json_start > 0:
            output = output[json_start:]
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise OciDataError("OCI CLI returned non-JSON output") from exc


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {})
    if isinstance(data, dict):
        return data.get("items", [])
    if isinstance(data, list):
        return data
    return []


def _tenancy_name(settings: Settings) -> str:
    payload = _run_oci(settings, ["iam", "tenancy", "get", "--tenancy-id", settings.oci_tenancy_ocid])
    data = payload.get("data", {})
    return data.get("name") or data.get("description") or "OCI tenancy"


def _regions(settings: Settings) -> list[str]:
    payload = _run_oci(settings, ["iam", "region", "list"])
    names = [item["name"] for item in payload.get("data", []) if item.get("name")]
    if settings.oci_region and settings.oci_region not in names:
        names.insert(0, settings.oci_region)
    return sorted(names)


def _compartments(settings: Settings) -> dict[str, str]:
    payload = _run_oci(
        settings,
        [
            "iam",
            "compartment",
            "list",
            "--compartment-id",
            settings.oci_tenancy_ocid,
            "--compartment-id-in-subtree",
            "true",
            "--access-level",
            "ACCESSIBLE",
            "--all",
        ],
    )
    compartments = {settings.oci_tenancy_ocid: "root"}

    for item in payload.get("data", []):
        if item.get("id") and item.get("name"):
            compartments[item["id"]] = item["name"]

    return compartments


def _resource_region(item: dict[str, Any], settings: Settings) -> str:
    identifier = item.get("identifier", "")
    parts = identifier.split(".")

    if len(parts) > 3 and parts[3]:
        return parts[3]

    return settings.oci_region or "unknown"


def _resource_service(resource_type: str) -> str:
    return SERVICE_BY_RESOURCE_TYPE.get(resource_type, "Governance")


def _resources(settings: Settings, compartments: dict[str, str], filters: dict[str, str]) -> list[Resource]:
    payload = _run_oci(
        settings,
        ["search", "resource", "structured-search", "--query-text", "query all resources", "--limit", "200"],
    )
    resources: list[Resource] = []

    for index, item in enumerate(_items(payload), start=1):
        resource_type = item.get("resource-type") or "Resource"
        service = _resource_service(resource_type)
        region = _resource_region(item, settings)
        compartment = compartments.get(item.get("compartment-id"), "unknown")
        lifecycle_state = item.get("lifecycle-state") or "available"
        display_name = item.get("display-name") or resource_type

        resource = Resource(
            id=item.get("identifier") or f"oci-live-{index}",
            name=display_name,
            service=service,
            shape=resource_type,
            region=region,
            compartment=compartment,
            monthlyCost=0,
            utilization=0 if lifecycle_state.upper() in {"STOPPED", "INACTIVE", "TERMINATED"} else 50,
            status=lifecycle_state,
            attached=True,
            provisioned={"timeCreated": item.get("time-created")} if item.get("time-created") else None,
        )

        if _matches_filters(resource, filters):
            resources.append(resource)

    return sorted(resources, key=lambda resource: (resource.service, resource.name.lower()))


def _usage_items(settings: Settings, group_by: list[str], start: date, end: date) -> list[dict[str, Any]]:
    try:
        import oci
    except ImportError as exc:
        raise OciDataError("OCI Python SDK is required for cost usage queries") from exc

    config = {
        "user": settings.oci_user_ocid,
        "fingerprint": settings.oci_fingerprint,
        "tenancy": settings.oci_tenancy_ocid,
        "region": settings.oci_region,
        "key_file": str(settings.oci_key_file),
    }
    usage_start = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    usage_end = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)

    try:
        oci.config.validate_config(config)
        client = oci.usage_api.UsageapiClient(config, timeout=(10, 30))
        details = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=settings.oci_tenancy_ocid,
            time_usage_started=usage_start,
            time_usage_ended=usage_end,
            granularity="DAILY",
            query_type="COST",
            group_by=group_by,
        )
        response = client.request_summarized_usages(details)
    except (
        oci.exceptions.InvalidConfig,
        oci.exceptions.RequestException,
        oci.exceptions.ServiceError,
        ValueError,
    ) as exc:
        raise OciDataError(f"OCI Usage API request failed: {exc}") from exc

    return [
        {
            "time-usage-started": item.time_usage_started.isoformat() if item.time_usage_started else None,
            "computed-amount": item.computed_amount,
            "service": item.service,
            "compartment-name": item.compartment_name,
            "region": item.region,
        }
        for item in (response.data.items or [])
    ]


def _float_value(item: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
    return 0


def _date_value(item: dict[str, Any]) -> str | None:
    value = item.get("time-usage-started") or item.get("timeUsageStarted")
    if not isinstance(value, str):
        return None
    return value[:10]


def _service_value(item: dict[str, Any]) -> str:
    return item.get("service") or item.get("service-name") or item.get("serviceName") or "Other"


def _compartment_value(item: dict[str, Any]) -> str:
    return item.get("compartment-name") or item.get("compartmentName") or item.get("compartment-path") or "root"


def _region_value(item: dict[str, Any], settings: Settings) -> str:
    return item.get("region") or settings.oci_region or "unknown"


def _cost_value(item: dict[str, Any]) -> float:
    return _float_value(item, "computed-amount", "computedAmount", "cost", "amount")


def _daily_costs(usage_items: list[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
    by_day = {date_key: 0.0 for date_key in ((start + timedelta(days=offset)).isoformat() for offset in range((end - start).days))}

    for item in usage_items:
        day = _date_value(item)
        if day:
            by_day[day] = by_day.get(day, 0) + _cost_value(item)

    return [{"date": day, "cost": money(value), "type": "actual"} for day, value in sorted(by_day.items())]


def _aggregate_usage(items: list[dict[str, Any]], key_fn) -> dict[str, float]:
    groups: dict[str, float] = {}

    for item in items:
        key = key_fn(item)
        groups[key] = money(groups.get(key, 0) + _cost_value(item))

    return groups


def _matches_filters(resource: Resource, filters: dict[str, str]) -> bool:
    service = filters.get("service", "all")
    region = filters.get("region", "all")
    return (service == "all" or resource.service == service) and (region == "all" or resource.region == region)


def _resource_aggregates(resources: list[Resource], field: str) -> dict[str, float]:
    groups: dict[str, float] = {}
    for resource in resources:
        key = getattr(resource, field)
        groups[key] = money(groups.get(key, 0) + resource.monthlyCost)
    return groups


def _recommendations(resources: list[Resource], has_cost_data: bool) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    untagged = [
        resource
        for resource in resources
        if resource.service != "Governance" and resource.compartment in {"root", "unknown"}
    ]

    if untagged:
        recommendations.append(
            {
                "id": "rec-oci-governance-root-compartment",
                "severity": "medium",
                "service": "Governance",
                "resourceId": untagged[0].id,
                "resourceName": untagged[0].name,
                "title": "Move workload resources out of root or unknown compartments",
                "evidence": f"{len(untagged)} live resource(s) are in root or unresolved compartments.",
                "summary": "Compartment ownership is a prerequisite for reliable chargeback and cleanup decisions.",
                "action": "Assign owners and move eligible resources into application compartments.",
                "estimatedMonthlySavings": 0,
                "estimatedAnnualSavings": 0,
                "confidence": 0.7,
                "risk": "low",
                "owner": "finops",
                "status": "open",
            }
        )

    if not has_cost_data:
        recommendations.append(
            {
                "id": "rec-oci-enable-usage-cost-data",
                "severity": "high",
                "service": "Billing",
                "resourceId": None,
                "resourceName": "OCI Usage API",
                "title": "Enable or verify OCI Usage API cost visibility",
                "evidence": "The live Usage API request succeeded but returned no cost rows for the selected period.",
                "summary": "Cost recommendations need billing data before savings estimates can be calculated.",
                "action": "Confirm the tenancy has usage records, billing permissions, and a date range with spend.",
                "estimatedMonthlySavings": 0,
                "estimatedAnnualSavings": 0,
                "confidence": 0.85,
                "risk": "low",
                "owner": "finops",
                "status": "open",
            }
        )

    return recommendations


def create_oci_cost_optimizer_data(filters: dict[str, str] | None, settings: Settings) -> dict[str, Any]:
    filters = filters or {}
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    tenancy = _tenancy_name(settings)
    regions = _regions(settings)
    compartments = _compartments(settings)
    resources = _resources(settings, compartments, filters)
    usage_items = _usage_items(settings, ["service"], start, end)
    daily_costs = _daily_costs(usage_items, start, end)
    forecast = _forecast_daily_costs(daily_costs) if any(point["cost"] for point in daily_costs) else []
    has_cost_data = any(_cost_value(item) for item in usage_items)
    spend_by_service = _aggregate_usage(usage_items, _service_value) if has_cost_data else _resource_aggregates(resources, "service")
    spend_by_compartment = _resource_aggregates(resources, "compartment")
    recommendations = _recommendations(resources, has_cost_data)
    current_run_rate = money(sum(point["cost"] for point in daily_costs))
    identified_savings = money(sum(item["estimatedMonthlySavings"] for item in recommendations))
    services = sorted(set(spend_by_service) | {resource.service for resource in resources})
    visible_compartments = sorted(set(spend_by_compartment) | set(compartments.values()))

    return {
        "meta": {
            "mode": "oci-live",
            "tenancy": tenancy,
            "period": f"{start.isoformat()} to {end.isoformat()}",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "regions": regions,
            "services": services,
            "compartments": visible_compartments,
            "filters": {
                "service": filters.get("service", "all"),
                "region": filters.get("region", "all"),
            },
            "costDataStatus": "available" if has_cost_data else "empty",
        },
        "summary": {
            "currentRunRate": current_run_rate,
            "projectedNextMonth": money(current_run_rate),
            "identifiedSavings": identified_savings,
            "optimizedRunRate": money(max(current_run_rate - identified_savings, 0)),
            "openRecommendations": len(recommendations),
            "highImpactRecommendations": len([item for item in recommendations if item["severity"] == "high"]),
            "monthOverMonthPercent": 0,
        },
        "dailyCosts": daily_costs,
        "forecast": forecast,
        "spendByService": spend_by_service,
        "spendByCompartment": spend_by_compartment,
        "resources": [asdict(resource) for resource in resources],
        "recommendations": recommendations,
    }


def answer_oci_copilot(question: str, filters: dict[str, str] | None, settings: Settings) -> str:
    data = create_oci_cost_optimizer_data(filters, settings)
    resource_count = len(data["resources"])
    cost_status = data["meta"].get("costDataStatus")
    run_rate = data["summary"]["currentRunRate"]

    if cost_status == "available":
        return (
            f"OCI live mode is connected to {data['meta']['tenancy']}. "
            f"I found {resource_count} visible resources and ${round(run_rate):,} in cost for {data['meta']['period']}."
        )

    return (
        f"OCI live mode is connected to {data['meta']['tenancy']} and found {resource_count} visible resources. "
        "The Usage API returned no cost rows for the selected period, so savings estimates are not available yet. "
        "Check billing permissions and whether this tenancy has generated usage in the date range."
    )
