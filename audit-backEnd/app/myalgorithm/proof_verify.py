from __future__ import annotations

from dataclasses import dataclass

from charm.toolbox.pairinggroup import G1

from .data_models import Challenge, Proof
from .protocol_utils import address_j_bytes, block_index_bytes
from .public_parameter import PP


@dataclass(frozen=True)
class ProofVerifyDetails:
    passed: bool
    left: str
    right: str


def proof_verify_details(challenge: Challenge, proof: Proof) -> ProofVerifyDetails:
    """
    ProofVerify(Chal, Proof) -> verification result plus both pairing sides.
    """

    group = PP["group"]
    pair_func = PP["pair"]

    H2 = PP["H2"]
    H3 = PP["H3"]

    g = PP["g"]
    u = PP["u"]
    y = PP["pk"]

    address = challenge.trapdoor.address

    left = pair_func(proof.T, g)

    prod = group.init(G1, 1)
    for item in challenge.Q:
        j = item.j
        vj = item.vj

        h3 = H3(group, block_index_bytes(j))
        h2 = H2(group, address_j_bytes(address, j))
        prod *= (h3 * h2) ** vj

    right_base = prod * (u ** proof.m)
    right = pair_func(right_base, y)

    return ProofVerifyDetails(
        passed=left == right,
        left=str(left),
        right=str(right),
    )


def proof_verify(challenge: Challenge, proof: Proof) -> bool:
    """
    Backward-compatible boolean verifier.
    """

    return proof_verify_details(challenge, proof).passed
