from charm.toolbox.pairinggroup import G1, ZR

from .public_parameter import PP
from .data_models import (
    SetupResult,
    SecureIndex,
    AuthenticatorSet,
    Challenge,
    Proof
)
from .protocol_utils import (
    expand_mask,
    xor_bytes,
    bytes_to_vector
)


def proof_gen(
    challenge: Challenge,
    secure_index: SecureIndex,
    setup_result: SetupResult,
    auth_set: AuthenticatorSet
) -> Proof:
    """
    实现 ProofGen(Chal, I, C, Φ) -> Proof

    云端根据挑战生成审计证明：
        Proof = {T, m}
    """

    group = PP["group"]

    address = challenge.trapdoor.address
    mask = challenge.trapdoor.mask

    if address not in secure_index.rows:
        raise ValueError("安全索引中不存在该 trapdoor 对应的地址")

    row = secure_index.rows[address]

    # =====================
    # 1. 恢复索引向量 v_w
    # =====================

    mask_expand = expand_mask(mask, len(row.encrypted_vector))
    vector_bytes = xor_bytes(row.encrypted_vector, mask_expand)
    vector = bytes_to_vector(vector_bytes)

    # S_w = {i | v_w[i] = 1}
    S_w = [
        i
        for i, bit in enumerate(vector, start=1)
        if bit == 1
    ]

    # =====================
    # 2. 计算 T 和 m
    # =====================

    T = group.init(G1, 1)
    m = group.init(ZR, 0)

    # 第一部分：Π_i∈Sw Π_j∈Q sigma_ij^vj
    for i in S_w:
        enc_file = setup_result.C[i - 1]
        file_id = enc_file.file_id

        for item in challenge.Q:
            j = item.j
            vj = item.vj

            sigma_ij = auth_set.authenticators[file_id][j]
            T *= sigma_ij ** vj

            block = enc_file.blocks[j - 1]
            cij = group.init(ZR, block.cij_int)

            m += cij * vj

    # 第二部分：Π_j∈Q V_w,j^vj
    for item in challenge.Q:
        j = item.j
        vj = item.vj

        V_wj = row.ral[j]
        T *= V_wj ** vj

    return Proof(
        T=T,
        m=m
    )