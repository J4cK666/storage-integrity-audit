from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel


try:
    from .home_shared import (
        DEFAULT_USER_ID,
        PENDING_STATUS,
        FileItem,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        make_file_id,
        now_text,
        parse_keywords,
        prepare_keyword_forms,
    )
    from ..myalgorithm.data_models import PlainFile
    from ..tools.save_to_cloud import save_to_cloud
    from ..tools.user_info import load_user_runtime_pp
except ImportError:
    from modules.home_shared import (
        DEFAULT_USER_ID,
        PENDING_STATUS,
        FileItem,
        connect,
        get_user_cloud_files_dir,
        init_audit_table,
        make_file_id,
        now_text,
        parse_keywords,
        prepare_keyword_forms,
    )
    from myalgorithm.data_models import PlainFile
    from tools.save_to_cloud import save_to_cloud
    from tools.user_info import load_user_runtime_pp


file_upload_router = APIRouter(prefix="/home", tags=["file-upload"])
DEFAULT_BLOCK_SIZE = 1024


class UploadResponse(BaseModel):
    message: str
    files: List[FileItem]


def _split_bytes(data: bytes, block_size: int) -> List[bytes]:
    if block_size <= 0:
        raise ValueError("block_size must be greater than 0")
    if not data:
        return [b""]
    return [
        data[index:index + block_size]
        for index in range(0, len(data), block_size)
    ]


def _algorithm_functions():
    try:
        from ..myalgorithm.auth_gen import auth_gen
        from ..myalgorithm.index_gen import index_gen
        from ..myalgorithm.setup import setup
    except ImportError:
        from myalgorithm.auth_gen import auth_gen
        from myalgorithm.index_gen import index_gen
        from myalgorithm.setup import setup

    return setup, index_gen, auth_gen


@file_upload_router.post("/files/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    keywords: List[str] = Form(...),
    user_id: str = Form(DEFAULT_USER_ID),
) -> UploadResponse:
    init_audit_table()
    cloud_files_dir = get_user_cloud_files_dir(user_id)

    if not files:
        raise HTTPException(status_code=400, detail="at_least_one_file_required")

    keyword_forms = prepare_keyword_forms(files, keywords)
    pp = load_user_runtime_pp(user_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="user_crypto_keys_not_found")

    upload_time = now_text()
    plain_files: List[PlainFile] = []
    uploaded_files: List[FileItem] = []

    for upload_file, raw_keywords in zip(files, keyword_forms):
        file_name = Path(upload_file.filename or "upload.bin").name
        parsed_keywords = parse_keywords(raw_keywords)
        if not parsed_keywords:
            raise HTTPException(status_code=400, detail=f"{file_name} missing_keywords")

        content = await upload_file.read()
        file_id = make_file_id(file_name, content, user_id)
        blocks = _split_bytes(content, DEFAULT_BLOCK_SIZE)

        plain_files.append(
            PlainFile(
                file_id=file_id,
                file_name=file_name,
                file_path="",
                blocks=blocks,
                keywords=parsed_keywords,
                size=len(content),
                block_count=len(blocks),
            )
        )
        uploaded_files.append(
            FileItem(
                file_id=file_id,
                file_name=file_name,
                file_size=len(content),
                upload_time=upload_time,
                keywords=parsed_keywords,
                audit_status=PENDING_STATUS,
                last_audit_time=None,
            )
        )

    try:
        setup, index_gen, auth_gen = _algorithm_functions()
        setup_result = setup(
            files=plain_files,
            k0=pp["k0"],
            Enc=pp["Enc"],
            block_size=DEFAULT_BLOCK_SIZE,
        )
        secure_index = index_gen(setup_result)
        auth_set = auth_gen(setup_result)
        save_result = save_to_cloud(
            setup_result=setup_result,
            secure_index=secure_index,
            auth_set=auth_set,
            user_id=user_id,
            cloud_dir=cloud_files_dir,
            group=pp["group"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"algorithm_upload_failed: {exc}") from exc

    with connect() as connection:
        for plain_file in plain_files:
            connection.execute(
                """
                INSERT OR REPLACE INTO audit_files (
                    file_id,
                    user_id,
                    file_name,
                    storage_path,
                    file_size,
                    upload_time,
                    keywords,
                    audit_status,
                    last_audit_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plain_file.file_id,
                    user_id,
                    plain_file.file_name,
                    str(save_result.encrypted_files[plain_file.file_id]),
                    plain_file.size,
                    upload_time,
                    json.dumps(plain_file.keywords, ensure_ascii=False),
                    PENDING_STATUS,
                    None,
                ),
            )

    return UploadResponse(message="upload_success", files=uploaded_files)
