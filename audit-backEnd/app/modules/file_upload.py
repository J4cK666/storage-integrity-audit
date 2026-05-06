from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

try:
    from ..config.config import UPLOAD_DIR
    from .home_shared import (
        DEFAULT_USER_ID,
        PENDING_STATUS,
        FileItem,
        cleanup_temp_file,
        connect,
        get_user_cloud_files_dir,
        init_home_tables,
        make_file_id,
        now_text,
        parse_keywords,
        prepare_keyword_forms,
    )
except ImportError:
    from config.config import UPLOAD_DIR
    from modules.home_shared import (
        DEFAULT_USER_ID,
        PENDING_STATUS,
        FileItem,
        cleanup_temp_file,
        connect,
        get_user_cloud_files_dir,
        init_home_tables,
        make_file_id,
        now_text,
        parse_keywords,
        prepare_keyword_forms,
    )


file_upload_router = APIRouter(prefix="/home", tags=["文件上传"])


class UploadResponse(BaseModel):
    message: str
    files: List[FileItem]


@file_upload_router.post("/files/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    keywords: List[str] = Form(...),
    user_id: str = Form(DEFAULT_USER_ID),
) -> UploadResponse:
    init_home_tables()
    cloud_files_dir = get_user_cloud_files_dir(user_id)

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    keyword_forms = prepare_keyword_forms(files, keywords)
    uploaded_files: List[FileItem] = []

    with connect() as connection:
        for upload_file, raw_keywords in zip(files, keyword_forms):
            file_name = Path(upload_file.filename or "upload.bin").name
            parsed_keywords = parse_keywords(raw_keywords)
            if not parsed_keywords:
                raise HTTPException(status_code=400, detail=f"{file_name} 缺少关键词")

            content = await upload_file.read()
            file_id = make_file_id(file_name, content, user_id)
            file_suffix = Path(file_name).suffix
            user_upload_dir = UPLOAD_DIR / user_id
            user_upload_dir.mkdir(parents=True, exist_ok=True)
            temp_path = user_upload_dir / f"{file_id}{file_suffix}.tmp"
            cloud_path = cloud_files_dir / f"{file_id}{file_suffix}"
            temp_path.write_bytes(content)
            temp_path.replace(cloud_path)
            cleanup_temp_file(temp_path)

            upload_time = now_text()
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
                    audit_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    user_id,
                    file_name,
                    str(cloud_path),
                    len(content),
                    upload_time,
                    json.dumps(parsed_keywords, ensure_ascii=False),
                    PENDING_STATUS,
                ),
            )

            uploaded_files.append(
                FileItem(
                    file_id=file_id,
                    file_name=file_name,
                    file_size=len(content),
                    upload_time=upload_time,
                    keywords=parsed_keywords,
                    audit_status=PENDING_STATUS,
                )
            )

    return UploadResponse(message="文件上传成功", files=uploaded_files)
