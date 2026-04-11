from fastapi import APIRouter

user_router = APIRouter(tags=["用户相关接口"], prefix="/user")

@user_router.post("/login")
def login():
    return {"message": "登录接口"}

@user_router.post("/register")
def register():
    return {"message": "注册接口"}
