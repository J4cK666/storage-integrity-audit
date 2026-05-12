from fastapi import HTTPException
from pydantic import BaseModel, Field

try:
    from ..config.database import init_user_tables
    from ..tools.user_info import get_user_info_by_username
    from .user_security import get_user_by_username, verify_password
except ImportError:
    from config.database import init_user_tables
    from tools.user_info import get_user_info_by_username
    from modules.user_security import get_user_by_username, verify_password


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginUser(BaseModel):
    account_id: str
    username: str
    cloud_folder: str
    pp: dict | None = None


class LoginResponse(BaseModel):
    message: str
    user: LoginUser


def login_user(request: LoginRequest) -> LoginResponse:
    init_user_tables()
    username = request.username.strip()
    password = request.password

    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    row = get_user_by_username(username)
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user_info = get_user_info_by_username(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User info not found")

    return LoginResponse(
        message="登录成功",
        user=LoginUser(
            account_id=user_info["account_id"],
            username=user_info["username"],
            cloud_folder=user_info["cloud_folder"],
            pp=user_info["pp"],
        ),
    )
