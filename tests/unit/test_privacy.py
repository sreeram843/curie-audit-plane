from curie_audit_plane.privacy import sanitize_comment


def test_sanitize_comment_keeps_safe_text():
    result = sanitize_comment("Looks consistent with the recorded evidence.")
    assert result["comment"] == "Looks consistent with the recorded evidence."
    assert result["comment_present"] is True
    assert result["comment_redacted"] is False
    assert result["comment_digest"]


def test_sanitize_comment_redacts_identifier_patterns():
    result = sanitize_comment("Patient TEST-00001 discussed home readings.")
    assert result["comment"] == ""
    assert result["comment_present"] is True
    assert result["comment_redacted"] is True
    assert "TEST-00001" not in result["comment"]
