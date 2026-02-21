import os
from fastapi import FastAPI, Request, HTTPException, Query
import httpx

app = FastAPI()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "dev-verify-token")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
BOT_PHONE_NUMBER = os.environ.get("BOT_PHONE_NUMBER")


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
):
    print("Verification request:",
          {"mode": hub_mode, "challenge": hub_challenge, "token": hub_verify_token})

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge or 0)

    raise HTTPException(status_code=403, detail="Verification failed")


BOT_PHONE_NUMBER = os.environ.get("BOT_PHONE_NUMBER")

@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("Incoming webhook:", data)

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

            # --- 👇 Detect mention ---
            mentioned = False

            context = message.get("context", {})
            mentioned_users = context.get("mentioned_users", [])

            if BOT_PHONE_NUMBER and BOT_PHONE_NUMBER in mentioned_users:
                mentioned = True

            if mentioned:
                reply_text = f"🤖 @satyasundar has been summoned."

                await send_whatsapp_message(from_number, reply_text)

    except Exception as e:
        print("Error:", e)

    return {"status": "ok"}

async def send_whatsapp_message(to_number: str, text: str):
    """
    Call WhatsApp Cloud API to send a text message.
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("WhatsApp env vars not set!")
        return

    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=payload)
        print("WhatsApp send status:", r.status_code, r.text)
        r.raise_for_status()
