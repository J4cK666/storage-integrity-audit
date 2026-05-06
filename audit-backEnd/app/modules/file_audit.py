from __future__ import annotations

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from .home_shared import (
        COMPLETE_STATUS,
        DEFAULT_USER_ID,
        AuditRecord,
        connect,
        init_home_tables,
        list_files,
        now_text,
        row_to_record,
    )
except ImportError:
    from modules.home_shared import (
        COMPLETE_STATUS,
        DEFAULT_USER_ID,
        AuditRecord,
        connect,
        init_home_tables,
        list_files,
        now_text,
        row_to_record,
    )


file_audit_router = APIRouter(prefix="/home", tags=["文件审计"])


class AuditRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    user_id: str = DEFAULT_USER_ID


class AuditFileResult(BaseModel):
    file_id: str
    file_name: str
    audit_result: str


class AuditResponse(BaseModel):
    keyword: str
    file_count: int
    audit_result: str
    audit_time: str
    files: List[AuditFileResult]


@file_audit_router.post("/audit", response_model=AuditResponse)
def audit_files(request: AuditRequest) -> AuditResponse:
    init_home_tables()

    keyword = request.keyword.strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    files = list_files(request.user_id)
    matched_files = [file for file in files if keyword in file.keywords]
    audit_time = now_text()

    if not matched_files:
        return AuditResponse(
            keyword=keyword,
            file_count=0,
            audit_result="未命中索引",
            audit_time=audit_time,
            files=[],
        )

    with connect() as connection:
        for file in matched_files:
            connection.execute(
                """
                UPDATE audit_files
                SET audit_status = ?
                WHERE file_id = ? AND user_id = ?
                """,
                (COMPLETE_STATUS, file.file_id, request.user_id),
            )
            connection.execute(
                """
                INSERT INTO audit_records (
                    record_id,
                    user_id,
                    file_id,
                    file_name,
                    keyword,
                    audit_result,
                    audit_time
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    request.user_id,
                    file.file_id,
                    file.file_name,
                    keyword,
                    COMPLETE_STATUS,
                    audit_time,
                ),
            )

    return AuditResponse(
        keyword=keyword,
        file_count=len(matched_files),
        audit_result="ProofVerify 通过",
        audit_time=audit_time,
        files=[
            AuditFileResult(
                file_id=file.file_id,
                file_name=file.file_name,
                audit_result=COMPLETE_STATUS,
            )
            for file in matched_files
        ],
    )


@file_audit_router.get("/audit-records", response_model=List[AuditRecord])
def get_audit_records(user_id: str = DEFAULT_USER_ID) -> List[AuditRecord]:
    init_home_tables()

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
