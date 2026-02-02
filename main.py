import os
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "dev-verify-token")


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = None,
    hub_challenge: str | None = None,
    hub_verify_token: str | None = None,
):
    """
    WhatsApp (Meta) calls this once when you set the webhook URL.
    You must echo back hub.challenge if the verify token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        # Meta expects the raw challenge, not JSON
        return int(hub_challenge or 0)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_message(request: Request):
    """
    WhatsApp will POST here whenever a message comes to your number.
    For now we just log and ack.
    """
    data = await request.json()
    print("Incoming webhook:", data)

    # Basic defensive parsing, because WhatsApp payloads are nested
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        messages = value.get("messages", [])
        if not messages:
            return {"status": "no messages"}

        message = messages[0]
        from_number = message["from"]
        msg_type = message["type"]

        if msg_type == "text":
            text_body = message["text"]["body"]
            print(f"Message from {from_number}: {text_body!r}")
        else:
            print(f"Non-text message from {from_number}: type={msg_type}")

    except (KeyError, IndexError, TypeError) as e:
        print("Error parsing webhook payload:", e)

    # WhatsApp just needs a 200 OK quickly; body isn't important
    return {"status": "ok"}
