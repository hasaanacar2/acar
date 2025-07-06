# 🌲 Orman Yangını Erken Uyarı Sistemi

Modern web teknolojileri ile geliştirilmiş, orman yangını risk analizi yapan interaktif harita uygulaması.

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

## 🚀 Hızlı Başlangıç

### 1. GitHub'a Yükleme

```bash
# Repository'yi GitHub'a yükleyin
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADINIZ/REPO_ADINIZ.git
git push -u origin main
```

### 2. Render.com Deployment

1. **[Render.com](https://render.com)**'da hesap oluşturun
2. **"New Web Service"** seçin
3. GitHub repository'nizi bağlayın
4. **Environment Variables** ekleyin:
   - `WEATHERAPI_KEY`: WeatherAPI.com API anahtarı
   - `GROQ_API_KEY`: Groq API anahtarı (LM analizi için gerekli)
5. **Build Command**: `pip install -r requirements.txt`
6. **Start Command**: `python app.py`
7. **Python Version**: 3.10.0
8. **Deploy** edin!

**Önemli**: LM analizi için GROQ_API_KEY zorunludur!

### 3. API Anahtarları

#### WeatherAPI.com
1. [WeatherAPI.com](https://www.weatherapi.com/)'da hesap oluşturun
2. Ücretsiz plan seçin (1000 istek/ay)
3. API anahtarınızı alın

#### Groq API
1. [Groq.com](https://console.groq.com/)'da hesap oluşturun
2. API anahtarınızı alın
3. Ücretsiz plan ile başlayın

## 🔧 Yerel Geliştirme

### Gereksinimler
- Python 3.9+
- pip

### Kurulum
```bash
# Repository'yi klonlayın
git clone https://github.com/KULLANICI_ADINIZ/REPO_ADINIZ.git
cd REPO_ADINIZ

# Virtual environment oluşturun
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Paketleri yükleyin
pip install -r requirements.txt

# Environment variables ayarlayın
cp env.example .env
# .env dosyasını düzenleyerek API anahtarlarınızı girin

# Uygulamayı çalıştırın
python app.py
```

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

## 📝 Lisans

MIT License

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun
3. Commit edin
4. Push edin
5. Pull Request açın 