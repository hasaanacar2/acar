# Orman Erken Uyarı Sistemi - Production Kurulum Rehberi

## 1. Gerekli Dosyalar
- Tüm Python dosyaları (app.py, auto_updater.py, lm_risk_analyzer.py, vs.)
- `templates/` ve `static/` klasörleri
- `requirements.txt`
- `.env` dosyası (veya sunucuda environment variable)

## 2. .env Dosyası
`.env.example` dosyasını `.env` olarak kopyalayın ve API anahtarlarınızı girin:
```
WEATHERAPI_KEY=senin_weatherapi_anahtarın
GROQ_API_KEY=senin_groq_anahtarın
```

## 3. Kurulum
```bash
pip install -r requirements.txt
```

## 4. Sunucuda Environment Variable Ayarlama (Alternatif)
- Linux/Mac:
  ```bash
  export WEATHERAPI_KEY=senin_weatherapi_anahtarın
  export GROQ_API_KEY=senin_groq_anahtarın
  ```
- Windows (PowerShell):
  ```powershell
  $env:WEATHERAPI_KEY="senin_weatherapi_anahtarın"
  $env:GROQ_API_KEY="senin_groq_anahtarın"
  ```

## 5. Uygulamayı Başlatma
```bash
python app.py
```

## 6. Production için Ekstra
- Flask debug ve reloader kapalıdır.
- Statik dosyalar ve GeoJSON yazma izinlerini kontrol edin.
- Gerekirse WSGI server (gunicorn, uWSGI) + Nginx ile çalıştırın.

## 7. Güvenlik
- .env dosyasını asla repoya eklemeyin!
- API anahtarlarını kimseyle paylaşmayın.

## 8. Sorunlar ve Destek
- Hata alırsanız logları kontrol edin.
- API limiti veya anahtar hatası için environment variable'ları tekrar kontrol edin. 