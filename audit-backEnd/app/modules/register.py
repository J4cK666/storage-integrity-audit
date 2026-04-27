import sqlite3

from fastapi import HTTPException
from pydantic import BaseModel, Field

try:
    from ..config.database import get_user_db_connection, init_user_tables
    from .user_security import (
        create_user_keys,
        ensure_user_cloud_folder,
        generate_account_id,
        get_user_by_username,
        make_password_hash,
    )
except ImportError:
    from config.database import get_user_db_connection, init_user_tables
    from modules.user_security import (
        create_user_keys,
        ensure_user_cloud_folder,
        generate_account_id,
        get_user_by_username,
        make_password_hash,
    )


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterUser(BaseModel):
    account_id: str
    username: str
    cloud_folder: str


class RegisterResponse(BaseModel):
    message: str
    user: RegisterUser


def register_user(request: RegisterRequest) -> RegisterResponse:
    init_user_tables()
    username = request.username.strip()
    password = request.password

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="用户名已存在")

    keys = create_user_keys()

    try:
        with get_user_db_connection() as connection:
            account_id = generate_account_id(connection)
            cloud_folder = ensure_user_cloud_folder(account_id)
            password_hash = make_password_hash(password)

            connection.execute(
                """
                INSERT INTO users (account_id, username, password_hash, cloud_folder)
                VALUES (?, ?, ?, ?)
                """,
                (account_id, username, password_hash, cloud_folder),
            )
            connection.execute(
                """
                INSERT INTO user_crypto_keys (
                    account_id,
                    public_key,
                    private_key,
                    g,
                    u,
                    k0,
                    k1,
                    k2
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    keys["public_key"],
                    keys["private_key"],
                    keys["g"],
                    keys["u"],
                    keys["k0"],
                    keys["k1"],
                    keys["k2"],
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="用户注册失败，账号或用户名已存在") from exc

    return RegisterResponse(
        message="注册成功",
        user=RegisterUser(
            account_id=account_id,
            username=username,
            cloud_folder=cloud_folder,
        ),
    )
