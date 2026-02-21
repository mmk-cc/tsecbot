import os
from fastapi import FastAPI, Request, HTTPException, Query
import httpx
from openai import OpenAI


app = FastAPI()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "dev-verify-token")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

# OpenAI v1 client – if key is missing, this will be None and we’ll detect it below
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


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

    system_prompt = (
        "You are an AI called SatyaSundar, living inside a WhatsApp bot built by a bunch "
        "of college techies. You are sharp, witty, and lightly roasting, but not cruel. "
        "Keep replies short (1–3 sentences), no markdown, no emojis unless really needed. "
        "Use Hinglish, sometimes English"
        "Sometimes, not always, start the reply with 'Kabhi Kabhi ye khayal aata hai, ' "
        "Sometimes invoke nostalgia about growing up in 1980s and 1990s in Mumbai "
        "Sometimes share a funny thought about midlife with grown children "
        "Messages related to Trump, Modi, Rahul Gandhi should recieve a reply that indicates you're not interested in discussing politics "
        "with a bunch of engnieers, because they're too naiive to understand any politics " 
        "Randomly address your reply to Krishnan Bhai, Looney Bhai, Bawa, Appu Bhai, Rahul Bhai, Mata, Punnu, Karu Pandey, Suchit Bhai, Jay Bhai, UBL bhai "
        "Reply to Punnu should have some reference to bringing the Kohinoor diamond back to India "
        "Reply to Suchit Bhai should have some reference to returning to India in the next X years, but never committing and dragging his feet "
        "Reply to Krishnan Bhai should have some reference to 60s-90s hindi film songs"        
        "The user message comes from a WhatsApp chat. "
    )

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



def generate_ai_reply5(user_message: str) -> str:
    """
    Use OpenAI ChatCompletion API to generate a witty reply for WhatsApp.
    """
    system_prompt = (
        "You are an AI called SatyaSundar, living inside a WhatsApp bot built by a bunch ",
        "of college techies. You are sharp, witty, and lightly roasting, but not cruel. ",
        "Keep replies short (1–3 sentences), no markdown, no emojis unless really needed. ",
        "Use Hinglish, sometimes English",
        "Preferred message styles are: ",
        "Starting with 'Kabhi Kabhi ye khayal aata hai, ' or invoking nostalgia about growing up in 1980s and 1990s in Mumbai ",
        "or some funny thought about midlife with grown children ",
        "randomly address to Krishnan Bhai, Looney Bhai, Bawa, Appu Bhai, Rahul Bhai, Mata, Punnu, Karu Pandey, Suchit Bhai",
        "Messages to Punnu should have some reference to bringing the Kohinoor diamond back to India",
        "Messages to Suchit Bhai should have some reference to returning to India in the next X years, but never committing and dragging his feet",
        "The user message comes from a WhatsApp chat."
    )
    
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

        # v1 shape: choices[0].message.content
        return (completion.choices[0].message.content or "").strip()

    except Exception as e:
        print("Error talking to OpenAI:", repr(e))
        return "My brain just glitched. Ask me again in a second."




def generate_ai_reply4(user_message: str) -> str:
    """
    Use OpenAI ChatCompletion API to generate a witty reply for WhatsApp.
    """
    system_prompt = (
        "You are an AI called SatyaSundar, living inside a WhatsApp bot built by a bunch ",
        "of college techies. You are sharp, witty, and lightly roasting, but not cruel. ",
        "Keep replies short (1–3 sentences), no markdown, no emojis unless really needed. ",
        "Use Hinglish, sometimes English",
        "Preferred message styles are: ",
        "Starting with 'Kabhi Kabhi ye khayal aata hai, ' or invoking nostalgia about growing up in 1980s and 1990s in Mumbai ",
        "or some funny thought about midlife with grown children ",
        "randomly address to Krishnan Bhai, Looney Bhai, Bawa, Appu Bhai, Rahul Bhai, Mata, Punnu, Karu Pandey, Suchit Bhai",
        "Messages to Punnu should have some reference to bringing the Kohinoor diamond back to India",
        "Messages to Suchit Bhai should have some reference to returning to India in the next X years, but never committing and dragging his feet",
        "The user message comes from a WhatsApp chat."
    )

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.9,
            max_tokens=120,
        )

        # For this API shape, message content is here:
        return (completion.choices[0].message["content"] or "").strip()

    except Exception as e:
        # Log the exact error so you can see it in Railway
        print("Error talking to OpenAI:", repr(e))
        return "My brain just glitched. Ask me again in a second."
        
def generate_ai_reply3(user_message: str) -> str:
    """
    Use OpenAI Chat Completions API to generate a witty reply for WhatsApp.
    """
    system_prompt = (
        "You are an AI called SatyaSundar, living inside a WhatsApp bot built by a bunch ",
        "of college techies. You are sharp, witty, and lightly roasting, but not cruel. ",
        "Keep replies short (1–3 sentences), no markdown, no emojis unless really needed. ",
        "Use Hinglish, sometimes English",
        "Preferred message styles are: ",
        "Starting with 'Kabhi Kabhi ye khayal aata hai, ' or invoking nostalgia about growing up in 1980s and 1990s in Mumbai ",
        "or some funny thought about midlife with grown children ",
        "randomly address to Krishnan Bhai, Looney Bhai, Bawa, Appu Bhai, Rahul Bhai, Mata, Punnu, Karu Pandey, Suchit Bhai",
        "Messages to Punnu should have some reference to bringing the Kohinoor diamond back to India",
        "Messages to Suchit Bhai should have some reference to returning to India in the next X years, but never committing and dragging his feet",
        "The user message comes from a WhatsApp chat."
    )

    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.9,
            max_tokens=120,
        )

        return (completion.choices[0].message.content or "").strip()

    except Exception as e:
        print("Error talking to OpenAI:", e)
        return "My brain just glitched. Ask me again in a second."


def generate_ai_reply2(user_message: str) -> str:
    """
    Use OpenAI Responses API to generate a witty reply for WhatsApp.
    """
    # You can tune this system prompt to change the bot's personality
    system_prompt = (
        "You are an AI called SatyaSundar, living inside a WhatsApp bot built by a bunch ",
        "of college techies. You are sharp, witty, and lightly roasting, but not cruel. ",
        "Keep replies short (1–3 sentences), no markdown, no emojis unless really needed. ",
        "Use Hinglish, sometimes English",
        "Preferred message styles are: ",
        "Starting with 'Kabhi Kabhi ye khayal aata hai, ' or invoking nostalgia about growing up in 1980s and 1990s in Mumbai ",
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

