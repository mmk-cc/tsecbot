from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/webhook")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print("Webhook payload:", body)
    return {"status": "received"}
