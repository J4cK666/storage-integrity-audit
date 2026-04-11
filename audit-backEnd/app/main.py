from fastapi import FastAPI
import string

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)

    # uvicorn main:app --reload
    # fastapi dev main:app --reload
    # python main.py
