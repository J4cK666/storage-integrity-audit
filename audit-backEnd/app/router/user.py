from fastapi import APIRouter

try:
    from ..modules.login import LoginRequest, LoginResponse, login_user
    from ..modules.register import RegisterRequest, RegisterResponse, register_user
except ImportError:
    from modules.login import LoginRequest, LoginResponse, login_user
    from modules.register import RegisterRequest, RegisterResponse, register_user

user_router = APIRouter(tags=["用户相关接口"], prefix="/user")


@user_router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    return login_user(request)


@user_router.post("/register", response_model=RegisterResponse)
def register(request: RegisterRequest) -> RegisterResponse:
    return register_user(request)
