from charm.toolbox.pairinggroup import G1

from .public_parameter import PP
from .data_models import Challenge, Proof
from .protocol_utils import address_j_bytes


def proof_verify(challenge: Challenge, proof: Proof) -> bool:
    """
    实现 ProofVerify(Chal, Proof) -> {0, 1}

    验证：
        e(T, g) == e((Π(H3(j) * H2(p(w)||j))^vj) * u^m, y)
    """

    group = PP["group"]
    pair_func = PP["pair"]

    H2 = PP["H2"]
    H3 = PP["H3"]

    g = PP["g"]
    u = PP["u"]
    y = PP["pk"]

    address = challenge.trapdoor.address

    # =====================
    # 左边 e(T, g)
    # =====================

    left = pair_func(proof.T, g)

    # =====================
    # 右边
    # =====================

    prod = group.init(G1, 1)

    for item in challenge.Q:
        j = item.j
        vj = item.vj

        h3 = H3(group, j.to_bytes(4, "big"))
        h2 = H2(group, address_j_bytes(address, j))

        prod *= (h3 * h2) ** vj

    right_base = prod * (u ** proof.m)
    right = pair_func(right_base, y)
    print("左边 e(T, g):", left)
    print("右边 e((Π(H3(j) * H2(p(w)||j))^vj) * u^m, y):", right)
    return left == right