from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from .config.database import init_user_tables
    from .modules.home import home_router, init_home_tables
    from .router.user import user_router
except ImportError:
    from config.database import init_user_tables
    from modules.home import home_router, init_home_tables
    from router.user import user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_user_tables()
    init_home_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(home_router)


@app.get("/")
def read_root():
    return {"message": "基于关键词的存储完整性审计系统后端服务"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

    # uvicorn main:app --reload
    # fastapi dev main:app --reload
    # python main.py
