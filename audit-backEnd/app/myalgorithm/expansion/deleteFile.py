from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:
    from ..data_models import (
        AuthenticatorSet,
        EncryptedFile,
        SecureIndex,
        SetupResult,
    )
    from ..protocol_utils import (
        expand_mask,
        id_j_bytes,
        keyword_to_bytes,
        vector_to_bytes,
        xor_bytes,
    )
except ImportError:
    from myalgorithm.data_models import (
        AuthenticatorSet,
        EncryptedFile,
        SecureIndex,
        SetupResult,
    )
    from myalgorithm.protocol_utils import (
        expand_mask,
        id_j_bytes,
        keyword_to_bytes,
        vector_to_bytes,
        xor_bytes,
    )


@dataclass(frozen=True)
class DeleteFileResult:
    setup_result: SetupResult
    secure_index: SecureIndex
    auth_set: AuthenticatorSet
    deleted_file_id: str
    deleted_file_index: int
    deleted_keywords: List[str]
    removed_keywords: List[str]
    encrypted_file: EncryptedFile


def _pp_value(name: str) -> Any:
    try:
        from ..public_parameter import PP
    except ImportError:
        from myalgorithm.public_parameter import PP

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


def _file_index_for_id(id_table: Mapping[int, str], file_id: str) -> int:
    for index, current_file_id in sorted(id_table.items()):
        if current_file_id == file_id:
            return index
    raise ValueError(f"file_id not found in file_table: {file_id}")


def _encrypted_file_for_id(setup_result: SetupResult, file_id: str) -> EncryptedFile:
    for enc_file in setup_result.C:
        if enc_file.file_id == file_id:
            return enc_file
    raise ValueError(f"encrypted file not found in setup_result.C: {file_id}")


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

    keyword_set = set()
    keywords_by_file: Dict[str, set[str]] = {}
    for _, file_id in sorted(id_table.items()):
        keywords = set(_normalize_keywords(file_keywords[file_id]))
        keywords_by_file[file_id] = keywords
        keyword_set.update(keywords)

    return {
        keyword: [
            1 if keyword in keywords_by_file[file_id] else 0
            for _, file_id in sorted(id_table.items())
        ]
        for keyword in sorted(keyword_set)
    }


def _index_address(keyword: str) -> bytes:
    PRP = _pp_value("PRP")
    k1 = _pp_value("k1")
    return PRP(k1, keyword_to_bytes(keyword))


def _encrypted_vector(keyword: str, vector: List[int]) -> tuple[bytes, bytes]:
    PRF = _pp_value("PRF")
    k2 = _pp_value("k2")

    address = _index_address(keyword)
    vector_bytes = vector_to_bytes(vector)
    mask = PRF(k2, address)
    return address, xor_bytes(vector_bytes, expand_mask(mask, len(vector_bytes)))


def _remove_vector_position(vector: Sequence[int], file_index: int) -> List[int]:
    if file_index < 1 or file_index > len(vector):
        raise ValueError(f"file_index out of vector range: {file_index}")
    return list(vector[: file_index - 1]) + list(vector[file_index:])


def _shift_file_table(id_table: Mapping[int, str], deleted_file_index: int) -> Dict[int, str]:
    remaining_file_ids = [
        file_id
        for index, file_id in sorted(id_table.items())
        if index != deleted_file_index
    ]
    return {
        index: file_id
        for index, file_id in enumerate(remaining_file_ids, start=1)
    }


def _remove_ral_factor(row, *, deleted_file_id: str, s: int) -> Dict[int, Any]:
    group = _pp_value("group")
    H1 = _pp_value("H1")
    x = _pp_value("sk")

    ral = dict(row.ral)
    for j in range(1, s + 1):
        if j not in ral:
            raise ValueError(f"RAL is missing block {j}")
        ral[j] = ral[j] * (H1(group, id_j_bytes(deleted_file_id, j)) ** x)
    return ral


def delete_file_from_package(
    *,
    setup_result: SetupResult,
    secure_index: SecureIndex,
    auth_set: AuthenticatorSet,
    file_keywords: Mapping[str, Sequence[str]],
    file_id: str,
) -> DeleteFileResult:
    """
    Physically delete F_r and shorten every keyword vector.

    The file order is taken from setup_result.file_table/id_table. After deleting
    position r, every file after r moves one slot forward while keeping its
    original file_id. RAL is incrementally updated for keywords contained in the
    deleted file with V'_w,j = V_w,j * H1(ID_r || j)^x.
    """

    if setup_result.s <= 0:
        raise ValueError("setup_result.s must be greater than 0")

    id_table = _ordered_id_table(setup_result)
    deleted_file_index = _file_index_for_id(id_table, file_id)
    deleted_file = _encrypted_file_for_id(setup_result, file_id)
    old_vectors = rebuild_keyword_vectors(
        id_table=id_table,
        file_keywords=file_keywords,
    )

    if secure_index.rows and len(secure_index.rows) != len(old_vectors):
        raise ValueError(
            "secure index row count does not match keyword records; "
            "cannot safely delete rows whose plaintext keywords are unknown"
        )

    if file_id not in file_keywords:
        raise ValueError(f"missing keyword record for deleted file: {file_id}")

    deleted_keywords = _normalize_keywords(file_keywords[file_id])
    deleted_keyword_set = set(deleted_keywords)
    updated_id_table = _shift_file_table(id_table, deleted_file_index)
    updated_vectors: Dict[str, List[int]] = {}
    removed_keywords: List[str] = []

    for keyword, old_vector in sorted(old_vectors.items()):
        new_vector = _remove_vector_position(old_vector, deleted_file_index)
        address, encrypted_vector = _encrypted_vector(keyword, new_vector)
        row = secure_index.rows.get(address)
        if row is None:
            raise ValueError(f"secure index row missing for keyword: {keyword}")

        if not any(new_vector):
            secure_index.rows.pop(address, None)
            removed_keywords.append(keyword)
            continue

        row.encrypted_vector = encrypted_vector
        if keyword in deleted_keyword_set:
            row.ral = _remove_ral_factor(
                row,
                deleted_file_id=file_id,
                s=setup_result.s,
            )
        if not row.keyword_debug:
            row.keyword_debug = keyword
        updated_vectors[keyword] = new_vector

    updated_C = [
        enc_file
        for enc_file in setup_result.C
        if enc_file.file_id != file_id
    ]
    if len(updated_C) != len(setup_result.C) - 1:
        raise ValueError(f"encrypted file list does not contain exactly one file_id: {file_id}")

    auth_set.authenticators.pop(file_id, None)

    updated_setup = SetupResult(
        C=updated_C,
        W=sorted(updated_vectors),
        V=updated_vectors,
        n=setup_result.n - 1,
        s=setup_result.s,
        file_table=updated_id_table.copy(),
        id_table=updated_id_table.copy(),
    )

    return DeleteFileResult(
        setup_result=updated_setup,
        secure_index=secure_index,
        auth_set=auth_set,
        deleted_file_id=file_id,
        deleted_file_index=deleted_file_index,
        deleted_keywords=deleted_keywords,
        removed_keywords=removed_keywords,
        encrypted_file=deleted_file,
    )


def delete_encrypted_file_from_cloud(
    *,
    cloud_dir: str | Path,
    file_id: str,
    missing_ok: bool = True,
) -> Path:
    safe_file_id = str(file_id).strip()
    if not safe_file_id or any(separator in safe_file_id for separator in ("/", "\\", ":", "\x00")):
        raise ValueError(f"unsafe file_id: {file_id!r}")

    path = Path(cloud_dir) / f"{safe_file_id}.enc"
    if path.exists():
        path.unlink()
    elif not missing_ok:
        raise FileNotFoundError(path)
    return path


def delete_file_database_record(
    *,
    connection,
    user_id: str,
    file_id: str,
) -> int:
    cursor = connection.execute(
        """
        DELETE FROM audit_files
        WHERE user_id = ? AND file_id = ?
        """,
        (user_id, file_id),
    )
    return int(cursor.rowcount)
