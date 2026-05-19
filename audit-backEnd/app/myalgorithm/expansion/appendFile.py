from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from charm.toolbox.pairinggroup import G1, ZR

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
    from ..public_parameter import PP
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
    from myalgorithm.public_parameter import PP
    from myalgorithm.setup import bytes_to_int_mod_q, split_file_by_s


@dataclass(frozen=True)
class AppendFileResult:
    setup_result: SetupResult
    secure_index: SecureIndex
    auth_set: AuthenticatorSet
    encrypted_file: EncryptedFile
    file_index: int
    existing_keywords: List[str]
    new_keywords: List[str]


def _pp_value(name: str) -> Any:
    if name not in PP:
        raise ValueError(f"PP['{name}'] is not initialized")
    return PP[name]


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


def rebuild_keyword_vectors(
    *,
    id_table: Mapping[int, str],
    file_keywords: Mapping[str, Sequence[str]],
) -> Dict[str, List[int]]:
    """
    Rebuild W and V from the database-side file keyword records.

    file_keywords maps file_id -> plaintext keywords from audit_files.keywords.
    """

    missing = [
        file_id
        for _, file_id in sorted(id_table.items())
        if file_id not in file_keywords
    ]
    if missing:
        raise ValueError(f"missing keyword records for existing files: {missing}")

    keyword_set: Set[str] = set()
    normalized_by_file: Dict[str, Set[str]] = {}
    for file_id in id_table.values():
        keywords = set(_normalize_keywords(file_keywords[file_id]))
        normalized_by_file[file_id] = keywords
        keyword_set.update(keywords)

    vectors: Dict[str, List[int]] = {}
    for keyword in sorted(keyword_set):
        vectors[keyword] = [
            1 if keyword in normalized_by_file[file_id] else 0
            for _, file_id in sorted(id_table.items())
        ]
    return vectors


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
    encrypted_vector = xor_bytes(vector_bytes, expand_mask(mask, len(vector_bytes)))
    return address, encrypted_vector


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


def _append_ral_factor(row: SecureIndexRow, *, file_id: str, s: int) -> Dict[int, Any]:
    group = _pp_value("group")
    H1 = _pp_value("H1")
    x = _pp_value("sk")

    ral = dict(row.ral)
    for j in range(1, s + 1):
        ral[j] = ral[j] * ((H1(group, id_j_bytes(file_id, j)) ** -1) ** x)
    return ral


def _authenticators_for_file(encrypted_file: EncryptedFile) -> Dict[int, Any]:
    group = _pp_value("group")
    H1 = _pp_value("H1")
    u = _pp_value("u")
    x = _pp_value("sk")

    authenticators: Dict[int, Any] = {}
    for block in encrypted_file.blocks:
        cij = group.init(ZR, block.cij_int)
        h1 = H1(group, id_j_bytes(encrypted_file.file_id, block.block_index))
        authenticators[block.block_index] = (h1 * (u ** cij)) ** x
    return authenticators


def append_file_to_package(
    *,
    setup_result: SetupResult,
    secure_index: SecureIndex,
    auth_set: AuthenticatorSet,
    file_keywords: Mapping[str, Sequence[str]],
    plain_file: PlainFile,
    k0: Optional[bytes] = None,
    Enc: Optional[Callable[[bytes, bytes], bytes]] = None,
    q: Optional[int] = None,
) -> AppendFileResult:
    """
    Append one file F_r, r = n + 1, without rebuilding the whole index.

    Existing W/V are recovered from audit_files via file_keywords. The new
    encrypted vector is written for every keyword, while RAL is updated
    incrementally for existing keywords contained in the new file.
    """

    if setup_result.s <= 0:
        raise ValueError("setup_result.s must be greater than 0")

    id_table = _ordered_id_table(setup_result)
    if plain_file.file_id in set(id_table.values()):
        raise ValueError(f"file_id already exists and cannot be appended: {plain_file.file_id}")

    old_vectors = rebuild_keyword_vectors(
        id_table=id_table,
        file_keywords=file_keywords,
    )
    if secure_index.rows and len(secure_index.rows) != len(old_vectors):
        raise ValueError(
            "secure index row count does not match keyword records; "
            "cannot safely update rows whose plaintext keywords are unknown"
        )

    n = setup_result.n
    file_index = n + 1
    updated_id_table = dict(id_table)
    updated_id_table[file_index] = plain_file.file_id

    encrypt_key = k0 if k0 is not None else _pp_value("k0")
    encrypt_func = Enc if Enc is not None else _pp_value("Enc")
    encrypted_file = _encrypt_plain_file(
        plain_file=plain_file,
        k0=encrypt_key,
        Enc=encrypt_func,
        s=setup_result.s,
        q=q,
    )

    new_keyword_set = set(_normalize_keywords(plain_file.keywords))
    old_keyword_set = set(old_vectors)
    all_keywords = sorted(old_keyword_set | new_keyword_set)
    updated_vectors: Dict[str, List[int]] = {}

    for keyword in all_keywords:
        old_vector = old_vectors.get(keyword, [0] * n)
        contains_new_file = keyword in new_keyword_set
        vector = old_vector + [1 if contains_new_file else 0]
        updated_vectors[keyword] = vector

        address, encrypted_vector = _encrypt_vector(keyword, vector)
        row = secure_index.rows.get(address)

        if row is None:
            row = SecureIndexRow(
                address=address,
                encrypted_vector=encrypted_vector,
                ral=_build_ral(
                    vector=vector,
                    id_table=updated_id_table,
                    address=address,
                    s=setup_result.s,
                ),
                keyword_debug=keyword,
            )
            secure_index.rows[address] = row
            continue

        row.encrypted_vector = encrypted_vector
        if contains_new_file:
            if all(j in row.ral for j in range(1, setup_result.s + 1)):
                row.ral = _append_ral_factor(
                    row,
                    file_id=plain_file.file_id,
                    s=setup_result.s,
                )
            else:
                row.ral = _build_ral(
                    vector=vector,
                    id_table=updated_id_table,
                    address=address,
                    s=setup_result.s,
                )
        if not row.keyword_debug:
            row.keyword_debug = keyword

    auth_set.authenticators[plain_file.file_id] = _authenticators_for_file(encrypted_file)

    updated_setup = SetupResult(
        C=list(setup_result.C) + [encrypted_file],
        W=all_keywords,
        V=updated_vectors,
        n=file_index,
        s=setup_result.s,
        file_table=updated_id_table.copy(),
        id_table=updated_id_table.copy(),
    )

    return AppendFileResult(
        setup_result=updated_setup,
        secure_index=secure_index,
        auth_set=auth_set,
        encrypted_file=encrypted_file,
        file_index=file_index,
        existing_keywords=sorted(old_keyword_set & new_keyword_set),
        new_keywords=sorted(new_keyword_set - old_keyword_set),
    )


def append_files_to_package(
    *,
    setup_result: SetupResult,
    secure_index: SecureIndex,
    auth_set: AuthenticatorSet,
    file_keywords: Mapping[str, Sequence[str]],
    plain_files: Sequence[PlainFile],
    k0: Optional[bytes] = None,
    Enc: Optional[Callable[[bytes, bytes], bytes]] = None,
    q: Optional[int] = None,
) -> List[AppendFileResult]:
    results: List[AppendFileResult] = []
    working_keywords: Dict[str, Sequence[str]] = dict(file_keywords)
    current_setup = setup_result

    for plain_file in plain_files:
        result = append_file_to_package(
            setup_result=current_setup,
            secure_index=secure_index,
            auth_set=auth_set,
            file_keywords=working_keywords,
            plain_file=plain_file,
            k0=k0,
            Enc=Enc,
            q=q,
        )
        results.append(result)
        current_setup = result.setup_result
        working_keywords[plain_file.file_id] = _normalize_keywords(plain_file.keywords)

    return results
