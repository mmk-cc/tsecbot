import os
from fastapi import FastAPI, Request, HTTPException, Query
import httpx
from openai import OpenAI

app = FastAPI()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "dev-verify-token")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

# OpenAI client – uses OPENAI_API_KEY from env
openai_client = OpenAI()


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

            # 🔑 Trigger: only respond to messages starting with /ai
            stripped = text_body.strip()
            if stripped.lower().startswith("/ai"):
                user_content = stripped[3:].strip()

                if not user_content:
                    reply_text = "👋 Send `/ai something` and I’ll say something clever about it."
                else:
                    # Call OpenAI to generate a witty reply
                    reply_text = generate_ai_reply(user_content)

                await send_whatsapp_message(from_number, reply_text)
        else:
            print(f"Non-text message from {from_number}: type={msg_type}")

    except (KeyError, IndexError, TypeError) as e:
        print("Error parsing webhook payload:", e)

    # Always ack quickly so WhatsApp is happy
    return {"status": "ok"}


def generate_ai_reply(user_message: str) -> str:
    """
    Use OpenAI Responses API to generate a witty reply for WhatsApp.
    """
    # You can tune this system prompt to change the bot's personality
    system_prompt = (
        "You are an AI called SatyaSundar, living inside a WhatsApp bot built by a bunch ",
        "of college techies. You are sharp, witty, and lightly roasting, but not cruel. ",
        "Keep replies short (1–3 sentences), no markdown, no emojis unless really needed. ",
        "Preferred message styles are: ",
        "Starting with "Kabhi Kabhi ye khayal aata hai" or invoking nostalgia about growing up in 1980s and 1990s in Mumbai ",
        "or some funny thought about midlife with grown children ",
        "randomly address to Krishnan Bhai, Looney Bhai, Bawa, Appu Bhai, Rahul Bhai, Mata, Punnu, Karu Pandey, Suchit Bhai",
        "Messages to Punnu should have some reference to bringing the Kohinoor diamond back to India",
        "Messages to Suchit Bhai should have some reference to returning to India in the next X years, but never committing and dragging his feet",
        "The user message comes from a WhatsApp chat."
    )

    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )  # :contentReference[oaicite:2]{index=2}

        # Extract the first text chunk from the output
        for item in response.output:
            if item.type == "message":
                for c in item.content:
                    # In responses API, text is in content[].text for output_text
                    if hasattr(c, "text"):
                        return c.text.strip()

        # Fallback if structure is unexpected
        return "My brain just glitched. Ask me again?"

    except Exception as e:
        print("Error talking to OpenAI:", e)
        return "My GPU is having an existential crisis. Try again in a moment."


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
