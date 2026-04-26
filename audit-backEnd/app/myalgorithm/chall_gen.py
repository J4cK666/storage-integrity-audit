import random

from charm.toolbox.pairinggroup import ZR

from .public_parameter import PP
from .data_models import Trapdoor, Challenge, ChallengeItem


def chall_gen(trapdoor: Trapdoor, s: int, c: int) -> Challenge:
    """
    实现 ChallGen(Tw) -> Chal

    :param trapdoor: 搜索陷门 Tw
    :param s: 统一块数
    :param c: 挑战块数量
    """

    if c <= 0:
        raise ValueError("挑战块数量 c 必须大于 0")

    if c > s:
        raise ValueError(f"挑战块数量 c 不能大于统一块数 s，当前 c={c}, s={s}")

    group = PP["group"]

    Q_index = random.sample(range(1, s + 1), c)

    Q = []

    for j in Q_index:
        vj = group.random(ZR)
        Q.append(
            ChallengeItem(
                j=j,
                vj=vj
            )
        )

    return Challenge(
        trapdoor=trapdoor,
        Q=Q
    )