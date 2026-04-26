from charm.toolbox.pairinggroup import G1

from .public_parameter import PP
from .data_models import SetupResult, SecureIndex, SecureIndexRow
from .protocol_utils import (
    keyword_to_bytes,
    vector_to_bytes,
    expand_mask,
    xor_bytes,
    id_j_bytes,
    address_j_bytes,
)


def index_gen(setup_result: SetupResult) -> SecureIndex:
    """
    实现 IndexGen(x, W, V) -> I

    输入：
        setup_result.W
        setup_result.V
        setup_result.id_table
        setup_result.s

    输出：
        SecureIndex
    """

    group = PP["group"]
    H1 = PP["H1"]
    H2 = PP["H2"]
    H3 = PP["H3"]
    PRP = PP["PRP"]
    PRF = PP["PRF"]

    k1 = PP["k1"]
    k2 = PP["k2"]
    x = PP["sk"]

    I = SecureIndex()

    for wk in setup_result.W:
        # =====================
        # 1. 计算地址 p(wk)
        # =====================
        wk_bytes = keyword_to_bytes(wk)
        address = PRP(k1, wk_bytes)

        # =====================
        # 2. 加密索引向量 ev_p(wk)
        # =====================
        vector = setup_result.V[wk]
        vector_bytes = vector_to_bytes(vector)

        mask = PRF(k2, address)
        mask_expand = expand_mask(mask, len(vector_bytes))

        encrypted_vector = xor_bytes(vector_bytes, mask_expand)

        # =====================
        # 3. 计算 S_wk
        # =====================
        S_wk = [
            i
            for i, bit in enumerate(vector, start=1)
            if bit == 1
        ]

        # =====================
        # 4. 计算 RAL: V_p(wk)
        # =====================
        ral = {}

        for j in range(1, setup_result.s + 1):
            # Π H1(ID_i || j)^-1
            prod_inv = group.init(G1, 1)

            for i in S_wk:
                file_id = setup_result.id_table[i]
                h1 = H1(group, id_j_bytes(file_id, j))
                prod_inv *= h1 ** -1

            h3 = H3(group, j.to_bytes(4, "big"))
            h2 = H2(group, address_j_bytes(address, j))

            base = prod_inv * h3 * h2
            V_wj = base ** x

            ral[j] = V_wj

        row = SecureIndexRow(
            address=address,
            encrypted_vector=encrypted_vector,
            ral=ral,
            keyword_debug=wk
        )

        I.rows[address] = row

    return I