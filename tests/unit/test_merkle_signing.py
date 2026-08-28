from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.integrity.merkle import merkle_proof, merkle_root, verify_merkle_proof
from curie_audit_plane.integrity.signing import generate_keypair, sign_hex, verify_signature


def test_inclusion_proof_verifies_and_detects_wrong_leaf():
    leaves = [sha256_hex(b"a"), sha256_hex(b"b"), sha256_hex(b"c")]
    root = merkle_root(leaves)
    proof = merkle_proof(leaves, 1)
    assert verify_merkle_proof(leaves[1], proof, root)
    assert not verify_merkle_proof(leaves[0], proof, root)


def test_single_leaf_merkle_root_is_the_leaf():
    leaf = sha256_hex(b"only")
    assert merkle_root([leaf]) == leaf


def test_signature_roundtrip_and_wrong_key_fails():
    root = merkle_root([sha256_hex(b"tx-root")])
    priv, pub = generate_keypair()
    _, other_pub = generate_keypair()
    signature = sign_hex(root, priv)
    assert verify_signature(root, signature, pub)
    assert not verify_signature(root, signature, other_pub)
