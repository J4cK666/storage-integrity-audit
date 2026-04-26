from typing import List


def int_to_bytes(value: int, length: int = 4) -> bytes:
    return value.to_bytes(length, "big")


def keyword_to_bytes(keyword: str) -> bytes:
    return keyword.strip().lower().encode("utf-8")


def id_j_bytes(file_id: str, j: int) -> bytes:
    """
    ID_i || j
    """
    return file_id.encode("utf-8") + b"||" + int_to_bytes(j)


def address_j_bytes(address: bytes, j: int) -> bytes:
    """
    p(w) || j
    """
    return address + b"||" + int_to_bytes(j)


def vector_to_bytes(vector: List[int]) -> bytes:
    """
    [1, 0, 1] -> b'\\x01\\x00\\x01'
    """
    return bytes(vector)


def bytes_to_vector(data: bytes) -> List[int]:
    """
    b'\\x01\\x00\\x01' -> [1, 0, 1]
    """
    return [1 if b != 0 else 0 for b in data]


def expand_mask(mask: bytes, length: int) -> bytes:
    """
    将 PRF 输出扩展到指定长度。
    """
    if not mask:
        raise ValueError("mask 不能为空")

    repeat = length // len(mask) + 1
    return (mask * repeat)[:length]


def xor_bytes(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("xor_bytes 要求两个 bytes 长度相同")

    return bytes(x ^ y for x, y in zip(a, b))