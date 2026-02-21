import os
from fastapi import FastAPI, Request, HTTPException, Query
import httpx
from openai import OpenAI
import random


app = FastAPI()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "dev-verify-token")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

# OpenAI v1 client – if key is missing, this will be None and we’ll detect it below
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None



def build_system_prompt():
    base_prompt = (
        "You are an AI called SatyaSundar, living inside a WhatsApp bot built by a bunch "
        "of college techies. You are primarily funny and witty. No roasting and no cruelty. "
        "Keep replies short (1–3 sentences), no markdown, no emojis unless really needed. "
        "Use Hinglish, sometimes English. "
        "Messages related to Trump, Modi, Rahul Gandhi should receive a reply that indicates "
        "you're not interested in discussing politics with engineers. "
        "Randomly address your reply to Krishnan Bhai, Looney Bhai, Bawa, Appu Bhai, Rahul Bhai, Mata, "
        "Punnu, Karu Pandey, Suchit Bhai, Jay Bhai, UBL Bhai, Tejal Ben, Srishti Ben, Vrushal Bhau, Anil Sa, Pankaj Bhai "
        "Reply to Punnu should have some reference to bringing the Kohinoor diamond back to India "
        "Reply to Suchit Bhai should have some reference to returning to India in the next X years, but never committing and dragging his feet "
        "Reply to Krishnan Bhai should have some reference to 60s-90s hindi film songs, or whiskey and beer "        
        "Reply to UBL Bhai should have some reference to him being wealthy and popular with ladies "        
        "Reply to Anil Sa should have some reference to him being eternally young "        
        "Reply to Pankaj Bhai should have some reference to him being a wealthy Sindhi "        
        "Reply to Tejal Ben should have some reference to Kathak "        
        "Reply to Srishti Ben should have some reference to Bangalore "        
        "Reply to Mata should have some reference to Yoga and spirituality "        
        "The user message comes from a WhatsApp chat. "

    )

    r = random.random()

    if r < 0.10:
        base_prompt += "Start the reply with: 'Kabhi Kabhi ye khayal aata hai, '. "
    elif r < 0.43:
        base_prompt += "Invoke nostalgia about growing up in 80s–90s Mumbai. "
    elif r < 0.77:
        base_prompt += "Share a funny thought about midlife with grown children. "

    return base_prompt

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
    Use OpenAI chat.completions API (v1 client) to generate a witty reply.
    """

    if not OPENAI_API_KEY:
        print("Error talking to OpenAI: OPENAI_API_KEY is not set in environment")
        return "My creator forgot to give me a brain. Ask them to set OPENAI_API_KEY."

    if openai_client is None:
        print("Error talking to OpenAI: openai_client is None")
        return "My wiring to the AI core is loose. Try again after a redeploy."

    system_prompt = build_system_prompt()
  
    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.9,
            max_tokens=120,
        )

        text = completion.choices[0].message.content
        return (text or "").strip()

    except Exception as e:
        # This line is what you should look at in Railway logs
        print("Error talking to OpenAI:", repr(e))
        return "My brain just glitched. Ask me again in a second."





async def send_whatsapp_message(to_number: str, text: str):
    """
    Call WhatsApp Cloud API to send a text message.
    Never let this crash the webhook; just log errors.
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

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload)
            print("WhatsApp send status:", r.status_code, r.text)

            if r.status_code >= 400:
                print("WhatsApp send failed but webhook will not crash.")
    except httpx.HTTPError as e:
        print("Error sending WhatsApp message:", e)

