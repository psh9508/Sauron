from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from src.apis.analyze import router as analyze_router

app = FastAPI()
app.include_router(analyze_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)