from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from curie_audit_plane.adapters.factory import completer_from_settings
from curie_audit_plane.config import settings
from curie_audit_plane.evaluation.cohort import (
    MAX_COHORT_SIZE,
    MIN_COHORT_SIZE,
    generate_synthetic_cohort,
)
from curie_audit_plane.evaluation.figure import render_cohort_metrics_svg
from curie_audit_plane.evaluation.report import build_evaluation_report
from curie_audit_plane.evaluation.study import run_cohort_study
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import HumanActionStatus
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def _pipeline() -> Pipeline:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.signing_key_path.parent.mkdir(parents=True, exist_ok=True)
    if settings.signing_key_path.exists() and settings.verifying_key_path.exists():
        private_key = settings.signing_key_path.read_bytes()
        public_key = settings.verifying_key_path.read_bytes()
    else:
        private_key, public_key = generate_keypair()
        settings.signing_key_path.write_bytes(private_key)
        settings.verifying_key_path.write_bytes(public_key)
        settings.verifying_key_path.chmod(0o644)
        settings.signing_key_path.chmod(0o600)
    return Pipeline(
        PipelineServices(
            audit=AuditStore(settings.audit_db_path),
            content=ProtectedContentStore(settings.protected_dir),
            private_key=private_key,
            public_key=public_key,
            key_id="cap-dev-key",
        ),
        completer=completer_from_settings(settings),
    )


def _cohort_size(value: str) -> int:
    size = int(value)
    if not MIN_COHORT_SIZE <= size <= MAX_COHORT_SIZE:
        raise argparse.ArgumentTypeError("encounters must be between 1 and 1000")
    return size


def _repetition_count(value: str) -> int:
    count = int(value)
    if not MIN_COHORT_SIZE <= count <= MAX_COHORT_SIZE:
        raise argparse.ArgumentTypeError("repetitions must be between 1 and 1000")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="curie-audit-plane")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run the synthetic FHIR fixture transaction")
    run.add_argument("--action", choices=["ACCEPT", "MODIFY", "REJECT"], default="ACCEPT")
    evaluate = sub.add_parser("evaluate", help="Run the reproducible paper evaluation")
    evaluate.add_argument("--output-dir", type=Path, default=Path("evaluation-results"))
    evaluate.add_argument("--encounters", type=_cohort_size, default=50)
    evaluate.add_argument("--repetitions", type=_repetition_count, default=1)
    sub.add_parser("setup", help="Generate local bearer tokens into .env")
    serve = sub.add_parser("serve", help="Start the local API")
    serve.add_argument("--host", default=settings.host)
    serve.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args(argv)
    if args.command == "setup":
        from curie_audit_plane.auth import write_generated_local_tokens

        write_generated_local_tokens(Path(".env"))
        print("Generated local admin and console tokens in .env. Restart the API and Vite console. Do not commit .env.")
        return 0
    if args.command == "evaluate":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="curie-evaluation-") as temp_dir:
            private_key, public_key = generate_keypair()
            pipeline = Pipeline(
                PipelineServices(
                    audit=AuditStore(Path(temp_dir) / "audit.sqlite"),
                    content=ProtectedContentStore(Path(temp_dir) / "protected"),
                    private_key=private_key,
                    public_key=public_key,
                    key_id="evaluation-key",
                ),
                completer=completer_from_settings(settings),
            )
            cohort_paths = generate_synthetic_cohort(
                pipeline.fixture_path,
                Path(temp_dir) / "cohort",
                count=args.encounters,
            )
            study = run_cohort_study(pipeline, cohort_paths, repetitions=args.repetitions)
            report = build_evaluation_report(pipeline, cohort_study=study)
            (args.output_dir / "evaluation-report.json").write_text(
                json.dumps(report.to_json_dict(), indent=2) + "\n",
                encoding="utf-8",
            )
            (args.output_dir / "evaluation-metrics.csv").write_text(
                report.to_csv(),
                encoding="utf-8",
            )
            (args.output_dir / "evaluation-cohort-metrics.svg").write_text(
                render_cohort_metrics_svg(study.to_json_dict()),
                encoding="utf-8",
            )
            pipeline.close()
        print(f"Evaluation report: {args.output_dir / 'evaluation-report.json'}")
        print(f"Evaluation metrics: {args.output_dir / 'evaluation-metrics.csv'}")
        print(f"Evaluation figure: {args.output_dir / 'evaluation-cohort-metrics.svg'}")
        return 0

    pipeline = _pipeline()
    if args.command == "run":
        result = pipeline.run_transaction(
            human_action=HumanActionStatus(args.action),
            actor="reviewer@curie.local",
        )
        print(result.transaction.transaction_id, result.transaction.status.value)
        print("verification", result.verification.status.value)
        return 0
    if args.command == "serve":
        import uvicorn

        from curie_audit_plane.api.app import create_app

        uvicorn.run(create_app(pipeline), host=args.host, port=args.port)
        return 0
    return 1


app = main

if __name__ == "__main__":
    raise SystemExit(main())
