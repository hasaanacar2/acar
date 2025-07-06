# 🌲 Orman Yangını Erken Uyarı Sistemi

Yapay zeka destekli orman yangını risk analizi ve erken uyarı sistemi.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🚀 Özellikler

- 🚀 **Otomatik Başlangıç Analizi**: Uygulama başladığında tüm alanlar otomatik analiz edilir
- 💾 **Akıllı Cache Sistemi**: Analiz sonuçları bir sonraki 12:00'a kadar cache'de tutulur
- 🔄 **Otomatik Güncelleme**: Her gün 12:00'de analizler yenilenir
- 📊 **Gerçek Zamanlı Durum**: Cache ve analiz durumu gerçek zamanlı gösterilir
- 🗺️ **İnteraktif Harita**: Leaflet.js ile modern harita arayüzü
- 🤖 **AI Destekli Analiz**: Groq API ile gelişmiş risk analizi
- 🌤️ **Hava Durumu Entegrasyonu**: WeatherAPI.com ile gerçek zamanlı hava verisi
- 🛡️ **Rate Limiting**: API limitlerini aşmamak için akıllı istek yönetimi
- **Gerçek zamanlı hava durumu** verileri (WeatherAPI.com)
- **1 gün önceki 12:00 verisi** ile başlangıç analizi
- **Yapay zeka destekli** risk analizi (Groq LM)
- **Otomatik güncelleme** sistemi
- **Cache yönetimi** ile performans optimizasyonu
- **Paralel işlem** ile hızlı analiz
- **Mobil uyumlu** web arayüzü
- **Kapatılabilir kutucuklar** (header ve legend)
- **Yangın noktası** entegrasyonu

## 📅 Otomatik Güncelleme Zamanlaması

Sistem her gün otomatik olarak güncellenir:

- **12:00** - Klasik risk güncellemesi (hava durumu bazlı)
- **13:00** - LM destekli risk güncellemesi (yapay zeka analizi)
- **13:01** - Cache temizleme (süresi dolmuş veriler)

### 🔄 Güncelleme Sırası

1. **12:00** - Temel hava durumu risk analizi
2. **13:00** - LM analizi başlar, cache güncellemeleri duraklar
3. **LM Analizi Tamamlanır** - Yeni cache uygulanır
4. **13:01** - Eski cache temizlenir

## 1. Gerekli Dosyalar
- Tüm Python dosyaları (app.py, auto_updater.py, lm_risk_analyzer.py, cache_manager.py)
- `templates/` ve `static/` klasörleri
- `requirements.txt`
- `env.example` dosyasını `.env` olarak kopyalayın

## 2. Environment Variables
`env.example` dosyasını `.env` olarak kopyalayın ve API anahtarlarınızı girin:
```
WEATHERAPI_KEY=your_weather_api_key_here
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

## 🌐 Kullanım

1. Web tarayıcısında `http://localhost:5000` adresine gidin
2. Harita üzerinde orman alanlarına tıklayın
3. Detaylı risk analizi sonuçlarını görüntüleyin

## 📊 Risk Seviyeleri

- 🟢 **Düşük Risk** - Normal koşullar
- 🟠 **Orta Risk** - Dikkatli olunmalı
- 🔴 **Yüksek Risk** - Acil durum
- 🟣 **Yayılma Riski** - Yangın yayılabilir

## 🔧 Teknik Detaylar

### Cache Sistemi

- **LM analizi sırasında** cache güncellemeleri duraklar
- **Analiz tamamlandıktan sonra** yeni cache uygulanır
- **13:00'dan sonra** cache geçerliliği kontrol edilir

### API Entegrasyonları

- **WeatherAPI.com** - Hava durumu verileri (dakikada 50 istek limiti)
- **Groq API** - Yapay zeka analizi (dakikada 90 istek limiti)
- **OpenStreetMap** - Harita verileri

### Rate Limiting

- **WeatherAPI**: Dakikada maksimum 50 istek
- **Groq API**: Dakikada maksimum 90 istek (100'ün altında güvenli marj)
- **Akıllı bekleme**: Limit aşıldığında otomatik bekleme
- **Thread-safe**: Çoklu işlem desteği

## 📱 Mobil Uyumluluk

- Responsive tasarım
- Touch-friendly arayüz
- Optimize edilmiş popup'lar
- Mobil cihazlarda mükemmel performans

## 🚀 Deployment

### Render.com

1. GitHub'a yükleyin
2. Render.com'da yeni Web Service oluşturun
3. Environment variables ekleyin
4. Deploy edin

### Diğer Platformlar

- Heroku
- Railway
- DigitalOcean App Platform

## 📝 Lisans

MIT License

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun
3. Commit edin
4. Push edin
5. Pull Request açın

## ⚡ Performans Optimizasyonları

### **Backend Optimizasyonları:**
- **Paralel işlem** (ThreadPoolExecutor ile 4 worker)
- **Hava durumu cache** (1 saat geçerli)
- **Timeout azaltma** (10s → 5s)
- **Sleep sürelerini azaltma** (500ms → 200ms)
- **Threaded Flask** sunucusu

### **Frontend Optimizasyonları:**
- **Debounced analiz** (100ms gecikme)
- **Periyodik güncelleme** (5 saniyede bir)
- **Lazy loading** popup içerikleri
- **Optimize edilmiş** mobil tasarım

### **Cache Sistemi:**
- **Çok seviyeli cache** (hava durumu + analiz)
- **Akıllı cache temizleme**
- **LM analizi sırasında** cache koruması 