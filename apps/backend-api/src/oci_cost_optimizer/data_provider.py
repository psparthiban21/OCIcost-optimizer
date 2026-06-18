from __future__ import annotations

from typing import Any

from .config import Settings
from .mock_data import answer_mock_copilot, create_mock_cost_optimizer_data
from .oci_data import OciDataError, answer_oci_copilot, create_oci_cost_optimizer_data


def create_cost_optimizer_data(filters: dict[str, str] | None, settings: Settings) -> dict[str, Any]:
    if settings.data_provider != "oci":
        return create_mock_cost_optimizer_data(filters)

    try:
        return create_oci_cost_optimizer_data(filters, settings)
    except OciDataError as error:
        data = create_mock_cost_optimizer_data(filters)
        data["meta"]["mode"] = "mock-fallback"
        data["meta"]["providerError"] = str(error)
        return data


def answer_copilot(question: str, filters: dict[str, str] | None, settings: Settings) -> str:
    if settings.data_provider != "oci":
        return answer_mock_copilot(question, filters)

    try:
        return answer_oci_copilot(question, filters, settings)
    except OciDataError as error:
        return (
            "OCI live mode is configured, but the live provider could not refresh data. "
            f"Reason: {error}\n\n"
            + answer_mock_copilot(question, filters)
        )
