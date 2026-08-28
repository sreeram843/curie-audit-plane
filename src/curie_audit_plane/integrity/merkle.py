from collections.abc import Sequence
from dataclasses import dataclass

from curie_audit_plane.integrity.hashing import sha256_hex


@dataclass(frozen=True)
class MerkleProof:
    index: int
    path: list[str]


def _combine(left: str, right: str) -> str:
    return sha256_hex(bytes.fromhex(left) + bytes.fromhex(right))


def merkle_root(leaves: Sequence[str]) -> str:
    if not leaves:
        raise ValueError("merkle_root requires at least one leaf")
    level = list(leaves)
    while len(level) > 1:
        nxt: list[str] = []
        for index in range(0, len(level), 2):
            if index + 1 >= len(level):
                nxt.append(level[index])
            else:
                nxt.append(_combine(level[index], level[index + 1]))
        level = nxt
    return level[0]


def merkle_proof(leaves: Sequence[str], index: int) -> MerkleProof:
    if index < 0 or index >= len(leaves):
        raise IndexError(index)
    path: list[str] = []
    level = list(leaves)
    idx = index
    while len(level) > 1:
        nxt: list[str] = []
        new_idx = idx
        for cursor in range(0, len(level), 2):
            parent_index = len(nxt)
            if cursor + 1 >= len(level):
                nxt.append(level[cursor])
                if idx == cursor:
                    new_idx = parent_index
                continue
            left, right = level[cursor], level[cursor + 1]
            if idx == cursor:
                path.append(f"R:{right}")
                new_idx = parent_index
            elif idx == cursor + 1:
                path.append(f"L:{left}")
                new_idx = parent_index
            nxt.append(_combine(left, right))
        idx = new_idx
        level = nxt
    return MerkleProof(index=index, path=path)


def verify_merkle_proof(leaf: str, proof: MerkleProof, root: str) -> bool:
    value = leaf
    for item in proof.path:
        if ":" not in item:
            return False
        side, sibling = item.split(":", 1)
        try:
            if side == "L":
                value = _combine(sibling, value)
            elif side == "R":
                value = _combine(value, sibling)
            else:
                return False
        except ValueError:
            return False
    return value == root
