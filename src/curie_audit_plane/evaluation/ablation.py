from curie_audit_plane.evaluation.fields import REQUIRED_FIELDS, reconstruct_fields
from curie_audit_plane.pipeline import TransactionResult

ABLATION_GROUPS = {
    "omit_input_manifests": ["input.manifest.resource_ids"],
    "omit_transformations": ["transformation.output_digest"],
    "omit_model_metadata": ["model.model_id", "model.prompt_version"],
    "omit_evidence": ["output.evidence_references"],
    "omit_proofs": [
        "integrity.event_hash",
        "integrity.previous_event_hash",
        "integrity.merkle_root",
        "integrity.signature",
        "integrity.key_id",
    ],
    "omit_human_provenance": ["human.action", "human.actor", "human.final_output_digest"],
}


def _arc_from_values(values: dict[str, object | None]) -> float:
    missing = [name for name in REQUIRED_FIELDS if not values.get(name)]
    return (len(REQUIRED_FIELDS) - len(missing)) / len(REQUIRED_FIELDS)


def run_ablations(result: TransactionResult) -> list[dict[str, object]]:
    full_values = reconstruct_fields(result)
    full_arc = _arc_from_values(full_values)
    rows: list[dict[str, object]] = [
        {
            "name": "full",
            "arc": full_arc,
            "delta": 0.0,
            "omitted_fields": [],
            "interpretation": "Complete recorded provenance.",
        }
    ]
    for name, omitted in ABLATION_GROUPS.items():
        values = dict(full_values)
        for field_name in omitted:
            values[field_name] = None
        arc = _arc_from_values(values)
        rows.append(
            {
                "name": name,
                "arc": arc,
                "delta": full_arc - arc,
                "omitted_fields": list(omitted),
                "interpretation": (
                    "Drop in reconstructability when the listed provenance class is omitted."
                ),
            }
        )
    return rows
