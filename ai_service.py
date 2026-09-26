import json
import os
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

async def summarize_laptop_post(text: str) -> str:
    if not client or not text:
        return "🔹 Noutbuk e'loni — Batafsil kanalda ko'rsatilgan"

    prompt = f"""
    Quyidagi noutbuk e'lonidan ma'lumotlarni ajratib ol va faqat JSON formatida qaytar.
    Hech qanday valyuta konvertatsiyasi qilma. Narx e'londa qanday yozilgan bo'lsa (masalan: $799, 10 000 000 so'm, 850$, kelishiladi), xuddi o'zini qoldir.

    Kutilayotgan JSON formati:
    {{
        "model": "Model nomi",
        "cpu": "Protsessor (masalan, i7-12700H)",
        "ram": "Operativ xotira (masalan, 16GB)",
        "gpu": "Videokarta (masalan, RTX 3060)",
        "short_desc": "1-3 so'zdan iborat qisqa ta'rif",
        "price": "E'londa ko'rsatilgan narx"
    }}

    E'lon matni:
    \"\"\"{text}\"\"\"
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        data = json.loads(response.text)
        
        model = data.get("model", "Noutbuk")
        cpu = data.get("cpu", "-")
        ram = data.get("ram", "-")
        gpu = data.get("gpu", "-")
        desc = data.get("short_desc", "Yaxshi holatda")
        price = data.get("price", "Narxi kelishiladi")

        return f"🔹 {model} ({cpu}, {ram}, {gpu}) — {desc} — {price}"
    except Exception as e:
        print(f"AI Xatolik: {e}")
        return f"🔹 Noutbuk e'loni — {text[:50]}..."
