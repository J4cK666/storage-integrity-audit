from typing import List, Dict, Callable, Optional
import hashlib

from .data_models import (
    PlainFile,
    EncryptedBlock,
    EncryptedFile,
    SetupResult
)


def bytes_to_int_mod_q(data: bytes, q: Optional[int] = None) -> int:
    """
    将密文块映射为整数，方便后续 AuthGen 中作为指数 cij 使用。
    """
    digest = hashlib.sha256(data).digest()
    value = int.from_bytes(digest, "big")

    if q is not None:
        return value % q

    return value


def setup(
    files: List[PlainFile],
    k0: bytes,
    Enc: Callable[[bytes, bytes], bytes],
    block_size: int = 4096,
    q: Optional[int] = None
) -> SetupResult:
    """
    实现 Setup(F) -> (C, W, V)

    files:
        read_file.py 读取并处理好的明文文件列表。

    k0:
        init 阶段生成的 AES 密钥。

    Enc:
        init 阶段定义的 AES 加密函数。
    """

    if not files:
        raise ValueError("files 不能为空")

    # =====================
    # 1. 文件数量 n 和统一块数 s
    # =====================

    n = len(files)

    # 使用统一 s，取所有文件中最大的块数
    s = max(file.block_count for file in files)

    # =====================
    # 2. 加密每个文件块，生成 C
    # =====================

    C: List[EncryptedFile] = []

    for file in files:
        encrypted_blocks: List[EncryptedBlock] = []

        for j in range(1, s + 1):
            if j <= file.block_count:
                plain_block = file.blocks[j - 1]
                is_padding = False
            else:
                # 短文件补齐到统一块数 s
                plain_block = b"\x00" * block_size
                is_padding = True

            ciphertext = Enc(k0, plain_block)
            cij_int = bytes_to_int_mod_q(ciphertext, q)

            encrypted_block = EncryptedBlock(
                file_id=file.file_id,
                file_name=file.file_name,
                block_index=j,
                ciphertext=ciphertext,
                cij_int=cij_int,
                is_padding=is_padding
            )

            encrypted_blocks.append(encrypted_block)

        encrypted_file = EncryptedFile(
            file_id=file.file_id,
            file_name=file.file_name,
            blocks=encrypted_blocks,
            original_block_count=file.block_count
        )

        C.append(encrypted_file)

    # =====================
    # 3. 构造关键词集合 W
    # =====================

    keyword_set = set()

    for file in files:
        for kw in file.keywords:
            keyword_set.add(kw)

    W = sorted(keyword_set)

    # =====================
    # 4. 构造索引向量集合 V
    # =====================

    V: Dict[str, List[int]] = {}

    for wk in W:
        vector = []

        for file in files:
            if wk in file.keywords:
                vector.append(1)
            else:
                vector.append(0)

        V[wk] = vector

    # =====================
    # 5. 文件编号表
    # =====================

    file_table = {
        i: file.file_name
        for i, file in enumerate(files, start=1)
    }

    id_table = {
        i: file.file_id
        for i, file in enumerate(files, start=1)
    }

    return SetupResult(
        C=C,
        W=W,
        V=V,
        n=n,
        s=s,
        block_size=block_size,
        file_table=file_table,
        id_table=id_table
    )



if __name__ == "__main__":
    pass