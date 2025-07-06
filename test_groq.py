import groq
import logging

logging.basicConfig(level=logging.INFO)

def test_groq_api():
    """Groq API'sini test eder"""
    try:
        api_key = "YOUR_GROQ_API_KEY_HERE"  # Buraya Groq API anahtarınızı ekleyin
        client = groq.Groq(api_key=api_key)
        model = "llama3-8b-8192"
        prompt = "Merhaba! Bu bir test mesajıdır. Yanıt veriyor musun?"
        print("Groq API'sine istek gönderiliyor...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=100,
            temperature=0.7
        )
        yanit = response.choices[0].message.content
        print("✅ Groq API çalışıyor!")
        print(f"Yanıt: {yanit}")
        return True
    except Exception as e:
        print(f"❌ Groq API hatası: {str(e)}")
        return False

if __name__ == "__main__":
    test_groq_api() 