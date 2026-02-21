import os
from fastapi import FastAPI, Request, HTTPException, Query
import httpx

app = FastAPI()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "dev-verify-token")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")


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

            # ✅ Only respond when message starts with /ai
            if text_body.strip().lower().startswith("/ai"):
                # Strip the trigger and build a simple reply
                user_content = text_body.strip()[3:].strip()
                if not user_content:
                    reply_text = "👋 Send `/ai something` and I’ll respond."
                else:
                    reply_text = f"🤖 You said: {user_content}"

                # Send the reply back
                await send_whatsapp_message(from_number, reply_text)
        else:
            print(f"Non-text message from {from_number}: type={msg_type}")

    except (KeyError, IndexError, TypeError) as e:
        print("Error parsing webhook payload:", e)

    # Always ack quickly so WhatsApp is happy
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
