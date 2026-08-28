from curie_audit_plane.privacy import COMMENT_CATEGORIES, opaque_identifier, sanitize_comment


def test_sanitize_comment_never_stores_free_text():
    result = sanitize_comment(
        "Looks consistent with the recorded evidence.",
        category="accept_as_recorded",
    )
    assert result["comment"] == ""
    assert result["comment_category"] == "accept_as_recorded"
    assert result["comment_present"] is True
    assert "Looks consistent" not in str(result)


def test_sanitize_comment_rejects_unknown_category():
    result = sanitize_comment("any text", category="not-a-category")
    assert result["comment_category"] == "unspecified"
    assert result["comment"] == ""


def test_sanitize_comment_redacts_identifier_patterns():
    result = sanitize_comment("Patient TEST-00001 discussed home readings.")
    assert result["comment"] == ""
    assert result["comment_present"] is True
    assert "TEST-00001" not in str(result)
    assert result["comment_category"] in COMMENT_CATEGORIES


def test_opaque_identifier_is_stable_and_not_raw():
    raw = "Patient/alt-99"
    token = opaque_identifier(raw)
    assert token.startswith("tok_")
    assert token == opaque_identifier(raw)
    assert "alt-99" not in token
    assert token != opaque_identifier("Patient/TEST-00001")
