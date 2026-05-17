from __future__ import annotations

import json
from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from .home_shared import (
        BROKEN_STATUS,
        COMPLETE_STATUS,
        DEFAULT_USER_ID,
        FILE_MISSING_STATUS,
        AuditRecord,
        FileItem,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        list_files,
        now_text,
        row_to_record,
    )
    from ..myalgorithm.data_models import Challenge, EncryptedFile
    from ..myalgorithm.protocol_utils import (
        bytes_to_vector,
        expand_mask,
        id_j_bytes,
        xor_bytes,
    )
    from ..tools.save_to_cloud import CloudPackage, load_from_cloud, load_index_metadata
    from ..tools.user_info import load_user_runtime_pp
except ImportError:
    from modules.home_shared import (
        BROKEN_STATUS,
        COMPLETE_STATUS,
        DEFAULT_USER_ID,
        FILE_MISSING_STATUS,
        AuditRecord,
        FileItem,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        list_files,
        now_text,
        row_to_record,
    )
    from myalgorithm.data_models import Challenge, EncryptedFile
    from myalgorithm.protocol_utils import (
        bytes_to_vector,
        expand_mask,
        id_j_bytes,
        xor_bytes,
    )
    from tools.save_to_cloud import CloudPackage, load_from_cloud, load_index_metadata
    from tools.user_info import load_user_runtime_pp


file_audit_router = APIRouter(prefix="/home", tags=["file_audit"])


class AuditRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    user_id: str = DEFAULT_USER_ID
    challenge_block_count: int = Field(1, ge=1)


class AuditOptionsResponse(BaseModel):
    min_block_count: int
    max_block_count: int


class AuditFileResult(BaseModel):
    file_id: str
    file_name: str
    audit_result: str


class AuditResponse(BaseModel):
    keyword: str
    challenge_block_count: int
    file_count: int
    audit_result: str
    audit_time: str
    files: List[AuditFileResult]


def _algorithm_functions():
    try:
        from ..myalgorithm.chall_gen import chall_gen
        from ..myalgorithm.proof_gen import proof_gen
        from ..myalgorithm.proof_verify import proof_verify
        from ..myalgorithm.trapdoor_gen import trapdoor_gen
    except ImportError:
        from myalgorithm.chall_gen import chall_gen
        from myalgorithm.proof_gen import proof_gen
        from myalgorithm.proof_verify import proof_verify
        from myalgorithm.trapdoor_gen import trapdoor_gen

    return trapdoor_gen, chall_gen, proof_gen, proof_verify


def _get_audit_max_block_count(user_id: str) -> int:
    cloud_dir = get_user_cloud_files_dir(user_id)
    try:
        metadata = load_index_metadata(user_id, cloud_dir)
    except FileNotFoundError:
        return 0
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"invalid_secure_index: {exc}") from exc

    try:
        return int(metadata.get("s", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="invalid_secure_index_block_count") from exc


def _load_cloud_package(user_id: str) -> CloudPackage:
    pp = load_user_runtime_pp(user_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="user_crypto_keys_not_found")

    cloud_dir = get_user_cloud_files_dir(user_id)
    try:
        return load_from_cloud(user_id, cloud_dir, group=pp["group"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"cloud_file_missing: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"invalid_cloud_data: {exc}") from exc


def _keyword_file_ids(challenge: Challenge, cloud_package: CloudPackage) -> List[str]:
    row = cloud_package.secure_index.rows.get(challenge.trapdoor.address)
    if row is None:
        return []

    mask_expand = expand_mask(challenge.trapdoor.mask, len(row.encrypted_vector))
    vector_bytes = xor_bytes(row.encrypted_vector, mask_expand)
    vector = bytes_to_vector(vector_bytes)

    file_ids: List[str] = []
    for index, bit in enumerate(vector, start=1):
        if bit == 1 and index in cloud_package.setup_result.id_table:
            file_ids.append(cloud_package.setup_result.id_table[index])

    return file_ids


def _file_lookup(files: List[FileItem]) -> Dict[str, FileItem]:
    return {file.file_id: file for file in files}


def _encrypted_file_lookup(cloud_package: CloudPackage) -> Dict[str, EncryptedFile]:
    return {
        encrypted_file.file_id: encrypted_file
        for encrypted_file in cloud_package.setup_result.C
    }


def _single_file_verify(
    file_id: str,
    encrypted_file: EncryptedFile,
    challenge: Challenge,
    cloud_package: CloudPackage,
) -> bool:
    from charm.toolbox.pairinggroup import G1, ZR

    try:
        from ..myalgorithm.public_parameter import PP
    except ImportError:
        from myalgorithm.public_parameter import PP

    group = PP["group"]
    pair_func = PP["pair"]
    h1_func = PP["H1"]
    g = PP["g"]
    u = PP["u"]
    pk = PP["pk"]

    authenticators = cloud_package.auth_set.authenticators.get(file_id)
    if authenticators is None:
        return False

    T = group.init(G1, 1)
    m = group.init(ZR, 0)
    prod = group.init(G1, 1)

    for item in challenge.Q:
        j = item.j
        vj = item.vj

        if j not in authenticators or j > len(encrypted_file.blocks):
            return False

        sigma_ij = authenticators[j]
        block = encrypted_file.blocks[j - 1]

        T *= sigma_ij ** vj
        m += group.init(ZR, block.cij_int) * vj
        prod *= h1_func(group, id_j_bytes(file_id, j)) ** vj

    left = pair_func(T, g)
    right = pair_func(prod * (u ** m), pk)
    return left == right


def _diagnose_files(
    file_ids: List[str],
    challenge: Challenge,
    cloud_package: CloudPackage,
) -> Dict[str, str]:
    encrypted_files = _encrypted_file_lookup(cloud_package)
    statuses: Dict[str, str] = {}

    for file_id in file_ids:
        encrypted_file = encrypted_files.get(file_id)
        if encrypted_file is None:
            statuses[file_id] = FILE_MISSING_STATUS
            continue

        statuses[file_id] = (
            COMPLETE_STATUS
            if _single_file_verify(file_id, encrypted_file, challenge, cloud_package)
            else BROKEN_STATUS
        )

    return statuses


def _record_files_payload(
    file_ids: List[str],
    statuses: Dict[str, str],
    db_files: Dict[str, FileItem],
) -> List[Dict[str, str]]:
    payload = []
    for file_id in file_ids:
        db_file = db_files.get(file_id)
        payload.append(
            {
                "file_id": file_id,
                "file_name": db_file.file_name if db_file else file_id,
                "audit_status": statuses.get(file_id, BROKEN_STATUS),
            }
        )
    return payload


def _save_audit_result(
    *,
    user_id: str,
    keyword: str,
    challenge_block_count: int,
    audit_result: str,
    audit_time: str,
    included_files: List[Dict[str, str]],
) -> None:
    with connect() as connection:
        for file in included_files:
            connection.execute(
                """
                UPDATE audit_files
                SET audit_status = ?,
                    last_audit_time = ?
                WHERE file_id = ? AND user_id = ?
                """,
                (file["audit_status"], audit_time, file["file_id"], user_id),
            )

        connection.execute(
            """
            INSERT INTO audit_records (
                record_id,
                user_id,
                keyword,
                challenge_block_count,
                included_files,
                audit_result,
                audit_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                user_id,
                keyword,
                challenge_block_count,
                json.dumps(included_files, ensure_ascii=False),
                audit_result,
                audit_time,
            ),
        )


@file_audit_router.get("/audit/options", response_model=AuditOptionsResponse)
def get_audit_options(user_id: str = DEFAULT_USER_ID) -> AuditOptionsResponse:
    init_audit_table()

    max_block_count = _get_audit_max_block_count(user_id)
    if max_block_count < 1:
        return AuditOptionsResponse(min_block_count=0, max_block_count=0)

    return AuditOptionsResponse(
        min_block_count=1,
        max_block_count=max_block_count,
    )


@file_audit_router.post("/audit", response_model=AuditResponse)
def audit_files(request: AuditRequest) -> AuditResponse:
    init_audit_table()

    keyword = request.keyword.strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword_required")

    cloud_package = _load_cloud_package(request.user_id)
    setup_result = cloud_package.setup_result
    if request.challenge_block_count > setup_result.s:
        raise HTTPException(status_code=400, detail="challenge_block_count_out_of_range")

    trapdoor_gen, chall_gen, proof_gen, proof_verify = _algorithm_functions()

    try:
        trapdoor = trapdoor_gen(keyword)
        challenge = chall_gen(
            trapdoor=trapdoor,
            s=setup_result.s,
            c=request.challenge_block_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_ids = _keyword_file_ids(challenge, cloud_package)
    db_files = _file_lookup(list_files(request.user_id))
    audit_time = now_text()

    if not file_ids:
        _save_audit_result(
            user_id=request.user_id,
            keyword=keyword,
            challenge_block_count=request.challenge_block_count,
            audit_result="no_keyword_match",
            audit_time=audit_time,
            included_files=[],
        )
        return AuditResponse(
            keyword=keyword,
            challenge_block_count=request.challenge_block_count,
            file_count=0,
            audit_result="no_keyword_match",
            audit_time=audit_time,
            files=[],
        )

    try:
        proof = proof_gen(
            challenge=challenge,
            secure_index=cloud_package.secure_index,
            setup_result=setup_result,
            auth_set=cloud_package.auth_set,
        )
        aggregate_passed = proof_verify(challenge=challenge, proof=proof)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"audit_algorithm_failed: {exc}") from exc

    if aggregate_passed:
        statuses = {file_id: COMPLETE_STATUS for file_id in file_ids}
        audit_result = COMPLETE_STATUS
    else:
        statuses = _diagnose_files(file_ids, challenge, cloud_package)
        audit_result = BROKEN_STATUS

    included_files = _record_files_payload(file_ids, statuses, db_files)
    _save_audit_result(
        user_id=request.user_id,
        keyword=keyword,
        challenge_block_count=request.challenge_block_count,
        audit_result=audit_result,
        audit_time=audit_time,
        included_files=included_files,
    )

    return AuditResponse(
        keyword=keyword,
        challenge_block_count=request.challenge_block_count,
        file_count=len(included_files),
        audit_result=audit_result,
        audit_time=audit_time,
        files=[
            AuditFileResult(
                file_id=file["file_id"],
                file_name=file["file_name"],
                audit_result=file["audit_status"],
            )
            for file in included_files
        ],
    )


@file_audit_router.get("/audit-records", response_model=List[AuditRecord])
def get_audit_records(user_id: str = DEFAULT_USER_ID) -> List[AuditRecord]:
    init_audit_table()

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM audit_records
            WHERE user_id = ?
            ORDER BY audit_time DESC
            """,
            (user_id,),
        ).fetchall()

    return [row_to_record(row) for row in rows]
