
from fastapi import FastAPI
app = FastAPI()

@app.post("/analyze")
def analyze(data: dict):
    return {"score": 50}
