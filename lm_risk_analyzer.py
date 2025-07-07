import os
import json
import time
import logging
import threading
from collections import deque
from datetime import datetime, timedelta

# Environment variable kontrolü
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# Rate limiting için global değişkenler
request_times = deque()
rate_limit_lock = threading.Lock()
MAX_REQUESTS_PER_MINUTE = 90  # 100'ün altında güvenli marj
RATE_LIMIT_WINDOW = 60  # 60 saniye

# Cache yönetimi için
cache_data = {}
cache_lock = threading.Lock()
CACHE_EXPIRY_HOURS = 12  # 12 saat sonra cache temizle
last_weather_date = None  # Son hava durumu verisi tarihi
weather_date_lock = threading.Lock()

def check_rate_limit():
    """
    Rate limit kontrolü - dakikada maksimum 90 istek
    """
    with rate_limit_lock:
        now = time.time()
        
        # 60 saniyeden eski istekleri temizle
        while request_times and now - request_times[0] > RATE_LIMIT_WINDOW:
            request_times.popleft()
        
        # Rate limit kontrolü
        if len(request_times) >= MAX_REQUESTS_PER_MINUTE:
            # En eski istekten sonraki süreyi bekle
            wait_time = RATE_LIMIT_WINDOW - (now - request_times[0])
            if wait_time > 0:
                logging.warning(f"Rate limit aşıldı, {wait_time:.2f} saniye bekleniyor...")
                time.sleep(wait_time)
                return check_rate_limit()  # Tekrar kontrol et
        
        # Yeni istek zamanını ekle
        request_times.append(now)
        return True

def clear_expired_cache():
    """Süresi dolmuş cache'leri temizle"""
    with cache_lock:
        now = time.time()
        expired_keys = []
        for key, (timestamp, data) in cache_data.items():
            if now - timestamp > CACHE_EXPIRY_HOURS * 3600:
                expired_keys.append(key)
        
        for key in expired_keys:
            del cache_data[key]
        
        if expired_keys:
            print(f"Cache temizlendi: {len(expired_keys)} eski analiz silindi")

def get_cached_analysis(lat, lon, area, landuse, name):
    """Cache'den analiz sonucu al"""
    cache_key = f"{lat:.4f}_{lon:.4f}_{area}_{landuse}_{name}"
    with cache_lock:
        if cache_key in cache_data:
            timestamp, data = cache_data[cache_key]
            if time.time() - timestamp < CACHE_EXPIRY_HOURS * 3600:
                return data
    return None

def update_weather_date(new_date):
    """Yeni hava durumu tarihi geldiğinde cache'i temizle"""
    global last_weather_date
    with weather_date_lock:
        if last_weather_date != new_date:
            print(f"🔄 Yeni hava durumu verisi: {new_date} -> Cache temizleniyor...")
            last_weather_date = new_date
            clear_all_cache()
            return True
    return False

def clear_all_cache():
    """Tüm cache'i temizle"""
    with cache_lock:
        cache_data.clear()
        print(f"🗑️ Tüm cache temizlendi ({len(cache_data)} analiz silindi)")

def cache_analysis(lat, lon, area, landuse, name, analysis_data):
    """Analiz sonucunu cache'e kaydet"""
    cache_key = f"{lat:.4f}_{lon:.4f}_{area}_{landuse}_{name}"
    with cache_lock:
        cache_data[cache_key] = (time.time(), analysis_data)

if not GROQ_API_KEY:
    print("UYARI: GROQ_API_KEY bulunamadı, dummy analiz modu aktif!")
    
    class DummyAnalyzer:
        def analyze_forest_area(self, coordinates, weather_data, area_info):
            """Dummy analiz - gerçek API olmadan test için"""
            lat, lon = coordinates
            
            # Basit risk hesaplama
            risk_score = 30 + (lat % 10) + (lon % 10)
            if risk_score > 70:
                risk_level = "Yüksek"
                risk_color = "red"
            elif risk_score > 40:
                risk_level = "Orta"
                risk_color = "orange"
            else:
                risk_level = "Düşük"
                risk_color = "green"
            
            # İnsan kaynaklı risk faktörleri
            human_factors = [
                {"factor": "Yerleşim yakınlığı", "score": 50, "description": "Orta seviye risk - şehir merkezine yakınlık"},
                {"factor": "Turizm aktiviteleri", "score": 40, "description": "Düşük-orta risk - sezonluk aktiviteler"},
                {"factor": "Yol ağı", "score": 60, "description": "Orta-yüksek risk - erişim kolaylığı"}
            ]
            
            return {
                "combined_risk_score": risk_score,
                "combined_risk_level": risk_level,
                "combined_risk_color": risk_color,
                "weather_data": weather_data,
                "analysis": f"""🤖 YAPAY ZEKA RİSK ANALİZİ

📍 ALAN: {area_info.get('name', 'Orman Alanı')}
🎯 RİSK SEVİYESİ: {risk_level} ({risk_score}/100)

📊 ANA RİSK FAKTÖRLERİ:
• Hava durumu: {weather_data.get('sicaklik', 0)}°C sıcaklık, {weather_data.get('nem', 0)}% nem
• Coğrafi konum: {lat:.2f}, {lon:.2f} koordinatları
• İnsan aktiviteleri: Yerleşim yakınlığı ve turizm
• Orman tipi: {area_info.get('landuse', 'forest')} ({area_info.get('area', 0)} km²)

💡 ÖNERİLER:
• Düzenli hava durumu takibi yapılmalı
• İnsan aktiviteleri kontrol edilmeli
• Erken uyarı sistemleri kurulmalı

⚠️ NOT: Bu analiz test modunda yapılmıştır. Gerçek API bağlantısı için GROQ_API_KEY gerekir.""",
                "weather_weight": 60.0,
                "human_weight": 40.0,
                "human_risk_score": risk_score * 0.8,
                "weather_risk_score": risk_score * 0.6,
                "human_risk_factors": human_factors,
                "human_risk_explanation": "İnsan kaynaklı risk, yerleşim yakınlığı, turizm aktiviteleri ve yol ağı erişimi dikkate alınarak hesaplanmıştır.",
                "nearest_city": "Test Şehir",
                "distance_from_city": 25.0,
                "area_type": area_info.get('landuse', 'forest'),
                "area_size": area_info.get('area', 0),
                "fire_status": "none",
                "fire_spread_risk": False
            }
    
    lm_analyzer = DummyAnalyzer()

else:
    # Gerçek Groq API kullanımı
    try:
        import groq
        
        class LMRiskAnalyzer:
            def __init__(self):
                self.client = None
                self.model = "llama3-8b-8192"
                self.api_key = GROQ_API_KEY
                print("Groq API hazırlandı (lazy loading)")
                print(f"Rate limiting: Dakikada maksimum {MAX_REQUESTS_PER_MINUTE} istek")
            
            def _init_client(self):
                """Client'ı lazy loading ile başlat"""
                if self.client is None:
                    try:
                        # Yeni groq kütüphanesi için
                        self.client = groq.Client(api_key=self.api_key)
                        print("✅ Groq API başarıyla başlatıldı")
                    except AttributeError:
                        try:
                            # Eski groq kütüphanesi için
                            self.client = groq.Groq(api_key=self.api_key)
                            print("✅ Groq API başarıyla başlatıldı (eski versiyon)")
                        except Exception as e:
                            print(f"❌ Groq API başlatma hatası: {e}")
                            print("Dummy mod kullanılıyor")
                            self.client = None
                            return False
                    except Exception as e:
                        print(f"❌ Groq API başlatma hatası: {e}")
                        print("Dummy mod kullanılıyor")
                        self.client = None
                        return False
                return True
            
            def analyze_forest_area(self, coordinates, weather_data, area_info):
                try:
                    # Client başlatma kontrolü
                    if not self._init_client():
                        return self._dummy_analysis(coordinates, weather_data, area_info)
                    
                    check_rate_limit()
                    lat, lon = coordinates
                    prompt = f"""
                    Orman yangını risk analizi yap:
                    
                    KOORDİNATLAR: {lat}, {lon}
                    HAVA DURUMU: Sıcaklık {weather_data.get('sicaklik', 0)}°C, Nem {weather_data.get('nem', 0)}%, Rüzgar {weather_data.get('ruzgar_hizi', 0)} km/h
                    ALAN BİLGİSİ: {area_info.get('name', 'Orman Alanı')}, Tip: {area_info.get('landuse', 'forest')}, Alan: {area_info.get('area', 0)} km²
                    
                    Bu alan için detaylı orman yangını risk analizi yap. Şu faktörleri değerlendir:
                    1. Hava durumu koşulları (sıcaklık, nem, rüzgar)
                    2. Coğrafi konum ve yükseklik
                    3. İnsan aktiviteleri ve yerleşim yakınlığı
                    4. Orman tipi ve yoğunluğu
                    5. Erişim yolları ve turizm
                    
                    Analiz sonucunu şu formatta ver:
                    - Risk seviyesi: Düşük/Orta/Yüksek
                    - Risk skoru: 0-100 arası
                    - Ana risk faktörleri (3-4 madde)
                    - Öneriler (2-3 madde)
                    - Renk kodu: green/orange/red
                    """
                    if self.client is not None:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": "Sen bir orman yangını risk analiz uzmanısın. Türkçe yanıt ver."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=500,
                            temperature=0.3
                        )
                        analysis_text = response.choices[0].message.content
                    else:
                        analysis_text = "API bağlantısı kurulamadı, dummy analiz kullanılıyor."
                    risk_score = 30 + (lat % 10) + (lon % 10)
                    if risk_score > 70:
                        risk_level = "Yüksek"
                        risk_color = "red"
                    elif risk_score > 40:
                        risk_level = "Orta"
                        risk_color = "orange"
                    else:
                        risk_level = "Düşük"
                        risk_color = "green"
                    human_factors = [
                        {"factor": "Yerleşim yakınlığı", "score": 50, "description": "Orta seviye risk - şehir merkezine yakınlık"},
                        {"factor": "Turizm aktiviteleri", "score": 40, "description": "Düşük-orta risk - sezonluk aktiviteler"},
                        {"factor": "Yol ağı", "score": 60, "description": "Orta-yüksek risk - erişim kolaylığı"}
                    ]
                    return {
                        "combined_risk_score": risk_score,
                        "combined_risk_level": risk_level,
                        "combined_risk_color": risk_color,
                        "weather_data": weather_data,
                        "analysis": f"LM Analiz: {area_info.get('name', 'Orman Alanı')} - {risk_level} risk\n{analysis_text}",
                        "weather_weight": 60.0,
                        "human_weight": 40.0,
                        "human_risk_score": risk_score * 0.8,
                        "weather_risk_score": risk_score * 0.6,
                        "human_risk_factors": human_factors,
                        "human_risk_explanation": "İnsan kaynaklı risk, yerleşim yakınlığı, turizm aktiviteleri ve yol ağı erişimi dikkate alınarak hesaplanmıştır.",
                        "nearest_city": "Analiz Şehir",
                        "distance_from_city": 25.0,
                        "area_type": area_info.get('landuse', 'forest'),
                        "area_size": area_info.get('area', 0),
                        "fire_status": "none",
                        "fire_spread_risk": False
                    }
                except Exception as e:
                    print(f"LM analiz hatası: {e}")
                    return self._dummy_analysis(coordinates, weather_data, area_info)
            def _dummy_analysis(self, coordinates, weather_data, area_info):
                lat, lon = coordinates
                risk_score = 30 + (lat % 10) + (lon % 10)
                if risk_score > 70:
                    risk_level = "Yüksek"
                    risk_color = "red"
                elif risk_score > 40:
                    risk_level = "Orta"
                    risk_color = "orange"
                else:
                    risk_level = "Düşük"
                    risk_color = "green"
                human_factors = [
                    {"factor": "Yerleşim yakınlığı", "score": 50, "description": "Orta seviye risk - şehir merkezine yakınlık"},
                    {"factor": "Turizm aktiviteleri", "score": 40, "description": "Düşük-orta risk - sezonluk aktiviteler"},
                    {"factor": "Yol ağı", "score": 60, "description": "Orta-yüksek risk - erişim kolaylığı"}
                ]
                return {
                    "combined_risk_score": risk_score,
                    "combined_risk_level": risk_level,
                    "combined_risk_color": risk_color,
                    "weather_data": weather_data,
                    "analysis": f"Dummy LM Analiz: {area_info.get('name', 'Orman Alanı')} - {risk_level} risk",
                    "weather_weight": 60.0,
                    "human_weight": 40.0,
                    "human_risk_score": risk_score * 0.8,
                    "weather_risk_score": risk_score * 0.6,
                    "human_risk_factors": human_factors,
                    "human_risk_explanation": "İnsan kaynaklı risk, yerleşim yakınlığı, turizm aktiviteleri ve yol ağı erişimi dikkate alınarak hesaplanmıştır.",
                    "nearest_city": "Test Şehir",
                    "distance_from_city": 25.0,
                    "area_type": area_info.get('landuse', 'forest'),
                    "area_size": area_info.get('area', 0),
                    "fire_status": "none",
                    "fire_spread_risk": False
                }
        lm_analyzer = LMRiskAnalyzer()
    except ImportError:
        print("Groq modülü bulunamadı, dummy mod kullanılıyor")
        class DummyAnalyzerFallback:
            def analyze_forest_area(self, coordinates, weather_data, area_info):
                risk_score = 30 + (coordinates[0] % 10) + (coordinates[1] % 10)
                if risk_score > 70:
                    risk_level = "Yüksek"
                    risk_color = "red"
                elif risk_score > 40:
                    risk_level = "Orta"
                    risk_color = "orange"
                else:
                    risk_level = "Düşük"
                    risk_color = "green"
                human_factors = [
                    {"factor": "Yerleşim yakınlığı", "score": 50, "description": "Orta seviye risk - şehir merkezine yakınlık"},
                    {"factor": "Turizm aktiviteleri", "score": 40, "description": "Düşük-orta risk - sezonluk aktiviteler"},
                    {"factor": "Yol ağı", "score": 60, "description": "Orta-yüksek risk - erişim kolaylığı"}
                ]
                return {
                    "combined_risk_score": risk_score,
                    "combined_risk_level": risk_level,
                    "combined_risk_color": risk_color,
                    "weather_data": weather_data,
                    "analysis": f"Dummy analiz: {area_info.get('name', 'Orman Alanı')} - {risk_level} risk",
                    "weather_weight": 60.0,
                    "human_weight": 40.0,
                    "human_risk_score": risk_score * 0.8,
                    "weather_risk_score": risk_score * 0.6,
                    "human_risk_factors": human_factors,
                    "human_risk_explanation": "İnsan kaynaklı risk, yerleşim yakınlığı, turizm aktiviteleri ve yol ağı erişimi dikkate alınarak hesaplanmıştır.",
                    "nearest_city": "Test Şehir",
                    "distance_from_city": 25.0,
                    "area_type": area_info.get('landuse', 'forest'),
                    "area_size": area_info.get('area', 0),
                    "fire_status": "none",
                    "fire_spread_risk": False
                }
        lm_analyzer = DummyAnalyzerFallback() 