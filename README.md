# Orman Erken Uyarı Sistemi - Production Kurulum Rehberi

## Özellikler
- 🚀 **Otomatik Başlangıç Analizi**: Uygulama başladığında tüm alanlar otomatik analiz edilir
- 💾 **Akıllı Cache Sistemi**: Analiz sonuçları bir sonraki 12:00'a kadar cache'de tutulur
- 🔄 **Otomatik Güncelleme**: Her gün 12:00'de analizler yenilenir
- 📊 **Gerçek Zamanlı Durum**: Cache ve analiz durumu gerçek zamanlı gösterilir
- 🗺️ **İnteraktif Harita**: Leaflet.js ile modern harita arayüzü

## 1. Gerekli Dosyalar
- Tüm Python dosyaları (app.py, auto_updater.py, lm_risk_analyzer.py, cache_manager.py)
- `templates/` ve `static/` klasörleri
- `requirements.txt`
- `env.example` dosyasını `.env` olarak kopyalayın

## 2. Environment Variables
`env.example` dosyasını `.env` olarak kopyalayın ve API anahtarlarınızı girin:
```
WEATHERAPI_KEY=your_weatherapi_key_here
GROQ_API_KEY=your_groq_api_key_here
```

## 3. Kurulum
```bash
# Gerekli paketleri yükle
pip install -r requirements.txt

# Environment variables ayarla
cp env.example .env
# .env dosyasını düzenleyerek API anahtarlarınızı girin
```

## 4. Development Ortamında Çalıştırma
```bash
python app.py
```

## 5. Production Deployment

### Render.com (Önerilen)
1. GitHub'a projeyi yükleyin
2. [Render.com](https://render.com)'da hesap oluşturun
3. "New Web Service" seçin
4. GitHub repository'nizi bağlayın
5. Environment variables ekleyin:
   - `WEATHERAPI_KEY`: WeatherAPI.com API anahtarı
   - `GROQ_API_KEY`: Groq API anahtarı
6. Build Command: `./build.sh`
7. Start Command: `python app.py`
8. Deploy edin!

### Heroku
```bash
# Heroku CLI ile
heroku create your-app-name
heroku config:set WEATHERAPI_KEY=your_key
heroku config:set GROQ_API_KEY=your_key
git push heroku main
```

### Docker
```bash
docker build -t orman-uyari-sistemi .
docker run -p 5000:5000 -e WEATHERAPI_KEY=your_key -e GROQ_API_KEY=your_key orman-uyari-sistemi
```

### VPS/Cloud Server
```bash
# Gunicorn ile
gunicorn wsgi:app -b 0.0.0.0:5000

# Systemd service olarak
sudo systemctl enable orman-uyari-sistemi
sudo systemctl start orman-uyari-sistemi
```

## 6. Environment Variables
- `WEATHERAPI_KEY`: WeatherAPI.com API anahtarı
- `GROQ_API_KEY`: Groq API anahtarı (LM analizi için)
- `FLASK_ENV`: production/development
- `PORT`: Sunucu portu (varsayılan: 5000)

## 7. Güvenlik
- `.env` dosyasını asla repoya eklemeyin!
- API anahtarlarını kimseyle paylaşmayın
- Production'da HTTPS kullanın

## 8. Monitoring ve Logs
- Cache istatistikleri: `/cache_stats`
- Analiz durumu: `/analysis_status`
- Log dosyaları: `auto_updater.log`

## 9. Sorun Giderme
- API limiti hatası: Environment variables'ı kontrol edin
- Cache sorunları: `/clear_cache` endpoint'ini kullanın
- Analiz durumu: Konsol çıktısını kontrol edin 