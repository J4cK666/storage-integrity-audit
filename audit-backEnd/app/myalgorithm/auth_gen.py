from charm.toolbox.pairinggroup import ZR

from .public_parameter import PP
from .data_models import SetupResult, AuthenticatorSet
from .protocol_utils import id_j_bytes


def auth_gen(setup_result: SetupResult) -> AuthenticatorSet:
    """
    实现 AuthGen(x, C) -> Φ

    对每个加密数据块 c_ij 生成验证器：
        sigma_ij = [H1(ID_i || j) · u^cij]^x
    """

    group = PP["group"]
    H1 = PP["H1"]

    u = PP["u"]
    x = PP["sk"]

    auth_set = AuthenticatorSet()

    for enc_file in setup_result.C:
        file_id = enc_file.file_id

        if file_id not in auth_set.authenticators:
            auth_set.authenticators[file_id] = {}

        for block in enc_file.blocks:
            j = block.block_index

            cij = group.init(ZR, block.cij_int)

            h1 = H1(group, id_j_bytes(file_id, j))
            sigma_ij = (h1 * (u ** cij)) ** x

            auth_set.authenticators[file_id][j] = sigma_ij

    return auth_set