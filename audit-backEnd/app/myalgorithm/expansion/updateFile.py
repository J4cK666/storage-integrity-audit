from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set

try:
    from ..data_models import (
        AuthenticatorSet,
        EncryptedBlock,
        EncryptedFile,
        PlainFile,
        SecureIndex,
        SecureIndexRow,
        SetupResult,
    )
    from ..protocol_utils import (
        address_j_bytes,
        block_index_bytes,
        expand_mask,
        id_j_bytes,
        keyword_to_bytes,
        vector_to_bytes,
        xor_bytes,
    )
    from ..setup import bytes_to_int_mod_q, split_file_by_s
except ImportError:
    from myalgorithm.data_models import (
        AuthenticatorSet,
        EncryptedBlock,
        EncryptedFile,
        PlainFile,
        SecureIndex,
        SecureIndexRow,
        SetupResult,
    )
    from myalgorithm.protocol_utils import (
        address_j_bytes,
        block_index_bytes,
        expand_mask,
        id_j_bytes,
        keyword_to_bytes,
        vector_to_bytes,
        xor_bytes,
    )
    from myalgorithm.setup import bytes_to_int_mod_q, split_file_by_s


@dataclass(frozen=True)
class UpdateFileResult:
    setup_result: SetupResult
    secure_index: SecureIndex
    auth_set: AuthenticatorSet
    encrypted_file: EncryptedFile
    file_id: str
    file_index: int
    old_keywords: List[str]
    new_keywords: List[str]
    same_keywords: List[str]
    deleted_keywords: List[str]
    added_keywords: List[str]
    new_system_keywords: List[str]
    removed_keywords: List[str]
    index_changed: bool


def _pp_value(name: str) -> Any:
    try:
        from ..public_parameter import PP
    except ImportError:
        from myalgorithm.public_parameter import PP

    if name not in PP:
        raise ValueError(f"PP['{name}'] is not initialized")
    return PP[name]


def _group_type(name: str) -> Any:
    from charm.toolbox.pairinggroup import G1, ZR

    return {"G1": G1, "ZR": ZR}[name]


def _normalize_keywords(keywords: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for keyword in keywords:
        value = str(keyword).strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _ordered_id_table(setup_result: SetupResult) -> Dict[int, str]:
    table = setup_result.id_table or setup_result.file_table
    ordered = {int(index): str(file_id) for index, file_id in table.items()}
    expected = list(range(1, len(ordered) + 1))
    actual = sorted(ordered)
    if actual != expected:
        raise ValueError(f"file indexes must be continuous from 1, got {actual}")
    if setup_result.n != len(ordered):
        raise ValueError(
            f"setup_result.n ({setup_result.n}) does not match file table size ({len(ordered)})"
        )
    return dict(sorted(ordered.items()))


def _file_index_for_id(id_table: Mapping[int, str], file_id: str) -> int:
    for index, current_file_id in sorted(id_table.items()):
        if current_file_id == file_id:
            return index
    raise ValueError(f"file_id not found in file_table: {file_id}")


def rebuild_keyword_vectors(
    *,
    id_table: Mapping[int, str],
    file_keywords: Mapping[str, Sequence[str]],
) -> Dict[str, List[int]]:
    missing = [
        file_id
        for _, file_id in sorted(id_table.items())
        if file_id not in file_keywords
    ]
    if missing:
        raise ValueError(f"missing keyword records for files: {missing}")

    keyword_set: Set[str] = set()
    normalized_by_file: Dict[str, Set[str]] = {}
    for _, file_id in sorted(id_table.items()):
        keywords = set(_normalize_keywords(file_keywords[file_id]))
        normalized_by_file[file_id] = keywords
        keyword_set.update(keywords)

    return {
        keyword: [
            1 if keyword in normalized_by_file[file_id] else 0
            for _, file_id in sorted(id_table.items())
        ]
        for keyword in sorted(keyword_set)
    }


def _encrypt_plain_file(
    *,
    plain_file: PlainFile,
    k0: bytes,
    Enc: Callable[[bytes, bytes], bytes],
    s: int,
    q: Optional[int] = None,
) -> EncryptedFile:
    file_data = b"".join(plain_file.blocks)
    plain_blocks = split_file_by_s(file_data, s)
    original_block_count = sum(1 for block in plain_blocks if block)

    encrypted_blocks: List[EncryptedBlock] = []
    for j, plain_block in enumerate(plain_blocks, start=1):
        ciphertext = Enc(k0, plain_block)
        encrypted_blocks.append(
            EncryptedBlock(
                file_id=plain_file.file_id,
                file_name=plain_file.file_name,
                block_index=j,
                ciphertext=ciphertext,
                cij_int=bytes_to_int_mod_q(ciphertext, q),
                is_padding=j > original_block_count,
            )
        )

    return EncryptedFile(
        file_id=plain_file.file_id,
        file_name=plain_file.file_name,
        blocks=encrypted_blocks,
        original_block_count=original_block_count,
    )


def _encrypt_vector(keyword: str, vector: List[int]) -> tuple[bytes, bytes]:
    PRP = _pp_value("PRP")
    PRF = _pp_value("PRF")
    k1 = _pp_value("k1")
    k2 = _pp_value("k2")

    address = PRP(k1, keyword_to_bytes(keyword))
    vector_bytes = vector_to_bytes(vector)
    mask = PRF(k2, address)
    return address, xor_bytes(vector_bytes, expand_mask(mask, len(vector_bytes)))


def _build_ral(
    *,
    vector: Sequence[int],
    id_table: Mapping[int, str],
    address: bytes,
    s: int,
) -> Dict[int, Any]:
    group = _pp_value("group")
    H1 = _pp_value("H1")
    H2 = _pp_value("H2")
    H3 = _pp_value("H3")
    x = _pp_value("sk")
    G1 = _group_type("G1")

    selected_indexes = [
        i
        for i, bit in enumerate(vector, start=1)
        if bit == 1
    ]

    ral: Dict[int, Any] = {}
    for j in range(1, s + 1):
        prod_inv = group.init(G1, 1)
        for i in selected_indexes:
            file_id = id_table[i]
            prod_inv *= H1(group, id_j_bytes(file_id, j)) ** -1

        base = (
            prod_inv
            * H3(group, block_index_bytes(j))
            * H2(group, address_j_bytes(address, j))
        )
        ral[j] = base ** x
    return ral


def _remove_ral_factor(row: SecureIndexRow, *, file_id: str, s: int) -> Dict[int, Any]:
    group = _pp_value("group")
    H1 = _pp_value("H1")
    x = _pp_value("sk")

    ral = dict(row.ral)
    for j in range(1, s + 1):
        if j not in ral:
            raise ValueError(f"RAL is missing block {j}")
        ral[j] = ral[j] * (H1(group, id_j_bytes(file_id, j)) ** x)
    return ral


def _add_ral_factor(row: SecureIndexRow, *, file_id: str, s: int) -> Dict[int, Any]:
    group = _pp_value("group")
    H1 = _pp_value("H1")
    x = _pp_value("sk")

    ral = dict(row.ral)
    for j in range(1, s + 1):
        if j not in ral:
            raise ValueError(f"RAL is missing block {j}")
        ral[j] = ral[j] * ((H1(group, id_j_bytes(file_id, j)) ** -1) ** x)
    return ral


def _authenticators_for_file(encrypted_file: EncryptedFile) -> Dict[int, Any]:
    group = _pp_value("group")
    H1 = _pp_value("H1")
    u = _pp_value("u")
    x = _pp_value("sk")
    ZR = _group_type("ZR")

    authenticators: Dict[int, Any] = {}
    for block in encrypted_file.blocks:
        cij = group.init(ZR, block.cij_int)
        h1 = H1(group, id_j_bytes(encrypted_file.file_id, block.block_index))
        authenticators[block.block_index] = (h1 * (u ** cij)) ** x
    return authenticators


def _replace_encrypted_file(
    *,
    encrypted_files: Sequence[EncryptedFile],
    file_index: int,
    encrypted_file: EncryptedFile,
) -> List[EncryptedFile]:
    if file_index < 1 or file_index > len(encrypted_files):
        raise ValueError(f"file_index out of encrypted file range: {file_index}")

    updated_C = list(encrypted_files)
    old_file = updated_C[file_index - 1]
    if old_file.file_id != encrypted_file.file_id:
        raise ValueError(
            "encrypted file order does not match file_table: "
            f"index {file_index} has {old_file.file_id}, expected {encrypted_file.file_id}"
        )

    updated_C[file_index - 1] = encrypted_file
    return updated_C


def update_file_in_package(
    *,
    setup_result: SetupResult,
    secure_index: SecureIndex,
    auth_set: AuthenticatorSet,
    file_keywords: Mapping[str, Sequence[str]],
    plain_file: PlainFile,
    k0: Optional[bytes] = None,
    Enc: Optional[Callable[[bytes, bytes], bytes]] = None,
    q: Optional[int] = None,
) -> UpdateFileResult:
    """
    Update an existing file without changing its file_id or file_index.

    The old keyword vectors are recovered from file_keywords, whose file_id
    entry must still contain the old keywords. plain_file.keywords contains the
    new keyword set after re-upload.
    """

    if setup_result.s <= 0:
        raise ValueError("setup_result.s must be greater than 0")

    id_table = _ordered_id_table(setup_result)
    file_id = plain_file.file_id
    file_index = _file_index_for_id(id_table, file_id)
    if file_id not in file_keywords:
        raise ValueError(f"missing old keyword record for updated file: {file_id}")

    old_vectors = rebuild_keyword_vectors(
        id_table=id_table,
        file_keywords=file_keywords,
    )
    if secure_index.rows and len(secure_index.rows) != len(old_vectors):
        raise ValueError(
            "secure index row count does not match old keyword records; "
            "cannot safely update rows whose plaintext keywords are unknown"
        )

    encrypt_key = k0 if k0 is not None else _pp_value("k0")
    encrypt_func = Enc if Enc is not None else _pp_value("Enc")
    encrypted_file = _encrypt_plain_file(
        plain_file=plain_file,
        k0=encrypt_key,
        Enc=encrypt_func,
        s=setup_result.s,
        q=q,
    )

    old_keywords = _normalize_keywords(file_keywords[file_id])
    new_keywords = _normalize_keywords(plain_file.keywords)
    old_keyword_set = set(old_keywords)
    new_keyword_set = set(new_keywords)
    same_keywords = sorted(old_keyword_set & new_keyword_set)
    deleted_keywords = sorted(old_keyword_set - new_keyword_set)
    added_keywords = sorted(new_keyword_set - old_keyword_set)
    new_system_keywords = sorted(new_keyword_set - set(old_vectors))
    index_changed = old_keyword_set != new_keyword_set

    updated_file_keywords: Dict[str, Sequence[str]] = dict(file_keywords)
    updated_file_keywords[file_id] = new_keywords
    new_vectors = rebuild_keyword_vectors(
        id_table=id_table,
        file_keywords=updated_file_keywords,
    )

    removed_keywords: List[str] = []
    updated_vectors: Dict[str, List[int]] = {}

    if index_changed:
        for keyword in sorted(set(old_vectors) | new_keyword_set):
            old_vector = old_vectors.get(keyword, [0] * setup_result.n)
            new_vector = new_vectors.get(keyword, [0] * setup_result.n)
            address, encrypted_vector = _encrypt_vector(keyword, new_vector)
            row = secure_index.rows.get(address)

            if not any(new_vector):
                secure_index.rows.pop(address, None)
                removed_keywords.append(keyword)
                continue

            if row is None:
                row = SecureIndexRow(
                    address=address,
                    encrypted_vector=encrypted_vector,
                    ral=_build_ral(
                        vector=new_vector,
                        id_table=id_table,
                        address=address,
                        s=setup_result.s,
                    ),
                    keyword_debug=keyword,
                )
                secure_index.rows[address] = row
                updated_vectors[keyword] = new_vector
                continue

            row.encrypted_vector = encrypted_vector
            if keyword in deleted_keywords:
                row.ral = _remove_ral_factor(
                    row,
                    file_id=file_id,
                    s=setup_result.s,
                )
            elif keyword in added_keywords:
                if old_vector[file_index - 1] != 0:
                    raise ValueError(f"keyword state conflict for added keyword: {keyword}")
                row.ral = _add_ral_factor(
                    row,
                    file_id=file_id,
                    s=setup_result.s,
                )

            if not row.keyword_debug:
                row.keyword_debug = keyword
            updated_vectors[keyword] = new_vector
    else:
        updated_vectors = old_vectors

    updated_C = _replace_encrypted_file(
        encrypted_files=setup_result.C,
        file_index=file_index,
        encrypted_file=encrypted_file,
    )
    auth_set.authenticators[file_id] = _authenticators_for_file(encrypted_file)

    updated_setup = SetupResult(
        C=updated_C,
        W=sorted(updated_vectors),
        V=updated_vectors,
        n=setup_result.n,
        s=setup_result.s,
        file_table=id_table.copy(),
        id_table=id_table.copy(),
    )

    return UpdateFileResult(
        setup_result=updated_setup,
        secure_index=secure_index,
        auth_set=auth_set,
        encrypted_file=encrypted_file,
        file_id=file_id,
        file_index=file_index,
        old_keywords=old_keywords,
        new_keywords=new_keywords,
        same_keywords=same_keywords,
        deleted_keywords=deleted_keywords,
        added_keywords=added_keywords,
        new_system_keywords=new_system_keywords,
        removed_keywords=removed_keywords,
        index_changed=index_changed,
    )

