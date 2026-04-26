from .public_parameter import PP
from .data_models import Trapdoor
from .protocol_utils import keyword_to_bytes


def trapdoor_gen(keyword: str) -> Trapdoor:
    """
    实现 TrapdoorGen(w) -> Tw

    Tw = { p(w), f(p(w)) }
    """

    PRP = PP["PRP"]
    PRF = PP["PRF"]

    k1 = PP["k1"]
    k2 = PP["k2"]

    w_bytes = keyword_to_bytes(keyword)

    address = PRP(k1, w_bytes)
    mask = PRF(k2, address)

    return Trapdoor(
        address=address,
        mask=mask
    )