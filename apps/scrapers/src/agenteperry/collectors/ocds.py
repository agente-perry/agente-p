"""OCDS Peru collector and parser."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any, TextIO, cast

from agenteperry.collectors.base import BulkDownloadCollector, CollectionResult


class OCDSPeruCollector(BulkDownloadCollector):
    """Collect and flatten OCDS releases into traceable source records."""

    def collect(
        self,
        download_dir: Path | None = None,
        input_path: Path | None = None,
        download_url: str | None = None,
        limit: int | None = None,
        **_: Any,
    ) -> list[CollectionResult]:
        if input_path is None:
            if not download_url or download_dir is None:
                raise ValueError("OCDS collector needs input_path or download_url + download_dir")
            input_path = self.download(download_url, download_dir)

        results: list[CollectionResult] = []
        checksum = self._file_checksum(input_path)
        for release in iter_ocds_releases(input_path):
            results.extend(flatten_ocds_release(release, input_path, checksum))
            if limit is not None and len(results) >= limit:
                return results[:limit]
        return results

    def _file_checksum(self, path: Path) -> str:
        digest = self.calculate_checksum(path.read_bytes())
        return digest


def iter_ocds_releases(path: Path) -> Iterator[dict[str, Any]]:
    """Yield OCDS releases from JSON, JSONL, or gzipped JSONL files."""
    suffixes = set(path.suffixes)
    if ".jsonl" in suffixes:
        with _open_text(path) as file_obj:
            for line in file_obj:
                cleaned = line.strip()
                if cleaned:
                    yield cast(dict[str, Any], json.loads(cleaned))
        return

    with _open_text(path) as file_obj:
        payload: object = json.load(file_obj)
    if isinstance(payload, list):
        items = cast(list[object], payload)
        for item in items:
            if isinstance(item, dict):
                yield cast(dict[str, Any], item)
        return
    if isinstance(payload, dict):
        payload_dict = cast(dict[str, Any], payload)
        releases_obj: object = payload_dict.get("releases")
        if isinstance(releases_obj, list):
            releases = cast(list[object], releases_obj)
            for release in releases:
                if isinstance(release, dict):
                    yield cast(dict[str, Any], release)
        else:
            yield payload_dict


def flatten_ocds_release(
    release: dict[str, Any], raw_path: Path | None = None, checksum: str | None = None
) -> list[CollectionResult]:
    """Flatten one OCDS release into source_records-compatible records."""
    ocid = _clean_text(release.get("ocid")) or _clean_text(release.get("id"))
    buyer = _as_dict(release.get("buyer"))
    tender = _as_dict(release.get("tender"))
    awards = _as_list(release.get("awards"))
    contracts = _as_list(release.get("contracts"))
    parties = _as_list(release.get("parties"))
    release_date = _parse_date(_clean_text(release.get("date")))
    entity_name = _clean_text(buyer.get("name"))
    tender_id = _clean_text(tender.get("id"))
    procedure_type = _clean_text(tender.get("procurementMethodDetails")) or _clean_text(
        tender.get("procurementMethod")
    )
    entity_ruc = _extract_ruc_from_parties(parties, role="buyer")
    region = _extract_region_from_parties(parties, role="buyer")

    records: list[CollectionResult] = []
    for award in awards:
        award_dict = _as_dict(award)
        suppliers = _as_list(award_dict.get("suppliers")) or [{}]
        award_date = _parse_date(_clean_text(award_dict.get("date"))) or release_date
        amount = _extract_amount(award_dict) or _extract_contract_amount(contracts)
        for supplier in suppliers:
            supplier_dict = _as_dict(supplier)
            supplier_name = _clean_text(supplier_dict.get("name"))
            supplier_ruc = _normalize_ruc(_clean_text(supplier_dict.get("id")))
            if not supplier_ruc:
                supplier_ruc = _extract_ruc_from_parties(parties, role="supplier")
            award_id = _clean_text(award_dict.get("id"))
            external_id = ":".join(part for part in [ocid, award_id, supplier_ruc] if part)
            records.append(
                CollectionResult(
                    source_code="ocds_peru",
                    external_id=external_id or ocid,
                    record_type="contract",
                    raw_data=release,
                    parsed_data={
                        "ocid": ocid,
                        "tender_id": tender_id,
                        "award_id": award_id,
                        "procedure_type": procedure_type,
                        "award_status": _clean_text(award_dict.get("status")),
                        "contracts_count": len(contracts),
                    },
                    raw_path=raw_path,
                    checksum=checksum,
                    content_type="application/ocds+json",
                    period_year=award_date.year if award_date else None,
                    region=region,
                    entity_name=entity_name,
                    entity_ruc=entity_ruc,
                    supplier_name=supplier_name,
                    supplier_ruc=supplier_ruc,
                    monto=amount,
                    fecha=award_date,
                    source_url=_clean_text(release.get("url")),
                    evidence_quote=_build_evidence_quote(entity_name, supplier_name, amount),
                )
            )

    if records:
        return records

    return [
        CollectionResult(
            source_code="ocds_peru",
            external_id=ocid,
            record_type="procedure",
            raw_data=release,
            parsed_data={"ocid": ocid, "tender_id": tender_id, "procedure_type": procedure_type},
            raw_path=raw_path,
            checksum=checksum,
            content_type="application/ocds+json",
            period_year=release_date.year if release_date else None,
            region=region,
            entity_name=entity_name,
            entity_ruc=entity_ruc,
            monto=_extract_amount(tender),
            fecha=release_date,
            source_url=_clean_text(release.get("url")),
            evidence_quote=f"Procedimiento OCDS {ocid or 'sin OCID'} publicado por {entity_name or 'entidad no identificada'}.",
        )
    ]


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def _as_dict(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _clean_text(value: object) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None


def _normalize_ruc(value: str | None) -> str | None:
    digits = "".join(ch for ch in value or "" if ch.isdigit())
    return digits if len(digits) == 11 else None


def _extract_amount(container: dict[str, Any]) -> float | None:
    value = _as_dict(container.get("value"))
    amount = value.get("amount")
    if amount is None:
        return None
    try:
        return float(amount)
    except (TypeError, ValueError):
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _build_evidence_quote(entity: str | None, supplier: str | None, amount: float | None) -> str:
    amount_text = f" por {amount:.2f}" if amount is not None else ""
    return f"{supplier or 'Proveedor no identificado'} gano contrato con {entity or 'entidad no identificada'}{amount_text}."


def _extract_ruc_from_parties(parties: list[object], role: str) -> str | None:
    """Extract RUC (11 digits) from parties with a specific role.

    RUC appears in two places per party:
      1. identifier.id with scheme=PE-RUC       (e.g. "20147704373")
      2. additionalIdentifiers[].id with scheme=PE-RUC (e.g. "20147704373")

    buyer.id field comes as PE-CONSUCODE-XXXX — NOT a RUC.
    """
    for party in parties:
        party_dict = _as_dict(party)
        roles: list[object] | None = party_dict.get("roles")
        if isinstance(roles, list) and role in roles:
            identifier: dict[str, Any] = cast(dict[str, Any], party_dict.get("identifier", {}))
            if identifier.get("scheme") == "PE-RUC":
                ruc = _normalize_ruc(cast("str | None", identifier.get("id")))
                if ruc:
                    return ruc
            for aid in party_dict.get("additionalIdentifiers", []):
                aid_dict = _as_dict(aid)
                if aid_dict.get("scheme") == "PE-RUC":
                    ruc = _normalize_ruc(cast("str | None", aid_dict.get("id")))
                    if ruc:
                        return ruc
    return None


def _extract_region_from_parties(parties: list[object], role: str) -> str | None:
    """Extract region/department from a party with a specific role."""
    for party in parties:
        party_dict = _as_dict(party)
        roles: list[object] | None = party_dict.get("roles")
        if isinstance(roles, list) and role in roles:
            address: dict[str, Any] = cast(dict[str, Any], party_dict.get("address", {}))
            if address:
                region = _clean_text(cast("str | None", address.get("department")))
                if region:
                    return region
    return None


def _extract_contract_amount(contracts: list[object]) -> float | None:
    """Use contracts[0].value.amount when awards has no amount."""
    if not contracts:
        return None
    contract_dict = _as_dict(contracts[0])
    amount = contract_dict.get("value", {}).get("amount")
    if amount is None:
        return None
    try:
        return float(amount)
    except (TypeError, ValueError):
        return None
