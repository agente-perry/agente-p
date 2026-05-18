"""CKAN API collector for public-data portals."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from json import JSONDecodeError
from typing import Any, cast

from agenteperry.collectors.base import CKANCollector, CollectionResult


class MefCkanCollector(CKANCollector):
    """Collect dataset metadata from MEF Datos Abiertos through CKAN APIs."""

    def collect(
        self,
        query: str | None = None,
        rows: int = 50,
        include_resources: bool = True,
        **_: Any,
    ) -> list[CollectionResult]:
        payload = ckan_package_search("https://datosabiertos.mef.gob.pe", query=query, rows=rows)
        datasets = cast(list[dict[str, Any]], payload.get("results", []))
        results: list[CollectionResult] = []
        for dataset in datasets:
            results.append(_dataset_result(dataset))
            if include_resources:
                for resource in _resources(dataset):
                    results.append(_resource_result(dataset, resource))
        return results


def ckan_package_search(base_url: str, query: str | None = None, rows: int = 50) -> dict[str, Any]:
    """Call CKAN package_search and return its result payload."""
    params = {"rows": str(rows)}
    if query:
        params["q"] = query
    last_error: Exception | None = None
    for api_prefix in ("api/3/action", "api/action"):
        url = f"{base_url.rstrip('/')}/{api_prefix}/package_search?{urllib.parse.urlencode(params)}"
        try:
            payload = _read_ckan_json(url)
            break
        except (JSONDecodeError, OSError, ValueError) as exc:
            last_error = exc
    else:
        raise ValueError(f"CKAN package_search failed for {base_url}: {last_error}") from last_error
    if not payload.get("success"):
        raise ValueError(f"CKAN package_search failed for {base_url}")
    result = payload.get("result")
    return cast(dict[str, Any], result if isinstance(result, dict) else {})


def _read_ckan_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"CKAN response is not an object: {url}")
    return cast(dict[str, Any], payload)


def _dataset_result(dataset: dict[str, Any]) -> CollectionResult:
    dataset_id = _text(dataset.get("id")) or _text(dataset.get("name"))
    title = _text(dataset.get("title")) or _text(dataset.get("name"))
    return CollectionResult(
        source_code="mef_datos_abiertos",
        external_id=dataset_id,
        record_type="dataset",
        raw_data=dataset,
        parsed_data={
            "name": _text(dataset.get("name")),
            "title": title,
            "notes": _text(dataset.get("notes")),
            "organization": _text(_as_dict(dataset.get("organization")).get("title")),
        },
        content_type="application/json",
        entity_name=title,
        source_url=_text(dataset.get("url")),
        evidence_quote=f"MEF Datos Abiertos publica el dataset {title or dataset_id or 'sin titulo'}.",
    )


def _resource_result(dataset: dict[str, Any], resource: dict[str, Any]) -> CollectionResult:
    dataset_name = _text(dataset.get("name")) or "dataset"
    resource_id = _text(resource.get("id"))
    resource_name = _text(resource.get("name")) or _text(resource.get("description"))
    return CollectionResult(
        source_code="mef_datos_abiertos",
        external_id=resource_id,
        record_type="dataset_resource",
        raw_data=resource,
        parsed_data={
            "dataset": dataset_name,
            "resource_name": resource_name,
            "format": _text(resource.get("format")),
            "url": _text(resource.get("url")),
        },
        content_type="application/json",
        entity_name=resource_name,
        source_url=_text(resource.get("url")),
        evidence_quote=f"MEF Datos Abiertos ofrece el recurso {resource_name or resource_id or 'sin nombre'} para {dataset_name}.",
    )


def _resources(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    resources_obj: object = dataset.get("resources")
    if not isinstance(resources_obj, list):
        return []
    resources = cast(list[object], resources_obj)
    return [cast(dict[str, Any], item) for item in resources if isinstance(item, dict)]


def _as_dict(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None
