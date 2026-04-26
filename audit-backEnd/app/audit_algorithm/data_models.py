# =====================
# 数据结构
# =====================
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict


# input data example
# files = [
#     {
#         "file_name": "F1",
#         "content": b"...file bytes...",
#         "keywords": ["cloud", "audit"]
#     },
#     {
#         "file_name": "F2",
#         "content": b"...",
#         "keywords": ["search", "encryption"]
#     }
# ]


# =========================================================
# read_file.py 使用的数据结构
# =========================================================

@dataclass
class PlainFile:
    """
    明文文件对象，对应论文中的 Fi

    file_id:
        文件唯一标识，对应后续公式中的 ID_i

    blocks:
        明文文件块 [Fi1, Fi2, ..., Fis]
        注意：在 read_file.py 中 blocks 还没有补齐统一 s。
        统一 s 的补齐操作放在 setup.py 中完成。
    """
    file_id: str
    file_name: str
    file_path: str
    blocks: List[bytes]
    keywords: List[str]
    size: int
    block_count: int


# =========================================================
# setup.py 输出的数据结构
# =========================================================

@dataclass
class EncryptedBlock:
    """
    加密后的文件块，对应论文中的 c_ij

    ciphertext:
        AES 加密后的密文块，真实上传到云端的数据。

    cij_int:
        将 ciphertext 映射成整数后的值。
        后续 AuthGen 中计算 u^cij 时使用。

    is_padding:
        是否是为了统一块数 s 补出来的块。
    """
    file_id: str
    file_name: str
    block_index: int
    ciphertext: bytes
    cij_int: int
    is_padding: bool = False


@dataclass
class EncryptedFile:
    """
    加密文件对象，对应论文中的 Ci

    blocks:
        [ci1, ci2, ..., cis]
    """
    file_id: str
    file_name: str
    blocks: List[EncryptedBlock]
    original_block_count: int


@dataclass
class SetupResult:
    """
    Setup(F) 的输出结果。

    C:
        加密数据块集合。

    W:
        关键词集合。

    V:
        索引向量集合。
        例如：
        {
            "cloud": [1, 0, 1],
            "audit": [0, 1, 0]
        }

    n:
        文件总数。

    s:
        统一块数。
    """
    C: List[EncryptedFile]
    W: List[str]
    V: Dict[str, List[int]]
    n: int
    s: int
    block_size: int
    file_table: Dict[int, str]
    id_table: Dict[int, str]


# =========================================================
# 后续 index_gen.py 可以使用的数据结构
# =========================================================

@dataclass
class SecureIndexRow:
    """
    安全索引中的一行。

    对应论文中的：
        I = { p(wk), ev_p(wk), V_p(wk) }

    address:
        p(wk)，关键词对应的安全索引地址。

    encrypted_vector:
        ev_p(wk)，加密后的索引向量。

    ral:
        V_p(wk)，关系认证标签 RAL。
        由于 RAL 是群元素列表，类型先用 List[Any]。
    """
    address: Any
    encrypted_vector: Any
    ral: List[Any] = field(default_factory=list)


@dataclass
class SecureIndex:
    """
    安全索引 I。

    rows:
        key 可以是 address，也可以是 keyword。
        建议后续实现时使用 address 作为 key。
    """
    rows: Dict[Any, SecureIndexRow] = field(default_factory=dict)


# =========================================================
# 后续 auth_gen.py 可以使用的数据结构
# =========================================================

@dataclass
class Authenticator:
    """
    单个数据块的验证器 s_ij。
    """
    file_id: str
    file_name: str
    block_index: int
    sigma: Any


@dataclass
class AuthenticatorSet:
    """
    验证器集合 Φ。

    结构示例：
        authenticators[file_id][j] = sigma_ij
    """
    authenticators: Dict[str, Dict[int, Any]] = field(default_factory=dict)


# =========================================================
# 后续 trapdoor / challenge / proof 可以使用的数据结构
# =========================================================

@dataclass
class Trapdoor:
    """
    搜索陷门 Tw。

    对应论文中的：
        Tw = { p(w), f(p(w)) }
    """
    address: Any
    mask: Any


@dataclass
class ChallengeItem:
    """
    单个挑战项。

    j:
        被挑战的块编号。

    vj:
        随机挑战系数。
    """
    j: int
    vj: Any


@dataclass
class Challenge:
    """
    审计挑战 Chal。

    对应论文中的：
        Chal = { Tw, {j, vj}_{j∈Q} }
    """
    trapdoor: Trapdoor
    Q: List[ChallengeItem]


@dataclass
class Proof:
    """
    云端生成的审计证明 Proof。

    对应论文中的：
        Proof = { T, m }
    """
    T: Any
    m: Any

@dataclass
class MyFile:
    file_id: str                                  # 文件ID，例如哈希值
    original_filename: Optional[str] = None  # 原始文件名
    data: List[Any] = field(default_factory=list)  # 加密文件块
    authenticator: List[Any] = field(default_factory=list)  # 审计标签(验证器)




GroupElement = Any  # 如果你用 PBC / Charm-Crypto，这里可以放群元素类型


@dataclass
class KeywordTag:
    """
    用户端关键词标签结构：
    一个 KeywordTag 对应一个关键词 wk。
    """

    keyword: str                                  # 明文关键词，用户端保存
    block_count: int                             # 每个文件的分块数 s
    file_ids: List[str] = field(default_factory=list)  # 包含该关键词的文件ID集合 Swk
    ral: List[GroupElement] = field(default_factory=list)  # RAL: [Vwk,1, ..., Vwk,s]

    



# =====================
# 数据结构
# =====================
