from pathlib import Path

from curie_audit_plane.auth import write_generated_local_tokens


def test_setup_generates_distinct_non_hardcoded_tokens(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("CAP_ADMIN_TOKEN=\nVITE_CAP_AUTH_TOKEN=\nCAP_REVIEWER_TOKEN=\n")
    first = write_generated_local_tokens(env_path)
    second = write_generated_local_tokens(env_path)
    assert first["CAP_ADMIN_TOKEN"]
    assert first["CAP_ADMIN_TOKEN"] == first["VITE_CAP_AUTH_TOKEN"]
    assert first["CAP_ADMIN_TOKEN"] != second["CAP_ADMIN_TOKEN"]
    text = env_path.read_text()
    assert "cap-dev-admin-token" not in text


def test_source_and_example_env_have_no_usable_tokens():
    root = Path(__file__).resolve().parents[2]
    example = (root / ".env.example").read_text()
    assert "CAP_ADMIN_TOKEN=\n" in example.replace("\r\n", "\n")
    assert "VITE_CAP_AUTH_TOKEN=\n" in example.replace("\r\n", "\n")
    for path in (root / "src").rglob("*.py"):
        assert "cap-dev-admin-token" not in path.read_text()
