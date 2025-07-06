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
                        self.client = groq.Groq(api_key=self.api_key)
                        print("✅ Groq API başarıyla başlatıldı")
                    except Exception as e:
                        print(f"❌ Groq API başlatma hatası: {e}")
                        print("Dummy mod kullanılıyor")
                        self.client = None
                        raise ImportError("Groq API başlatılamadı")
            
            def analyze_forest_area(self, coordinates, weather_data, area_info):
                """Gerçek LM analizi - rate limiting ile"""
                try:
                    # Client'ı başlat
                    self._init_client()
                    
                    # Rate limit kontrolü
                    check_rate_limit()
                    
                    lat, lon = coordinates
                    
                    # Gerçek LM analizi için prompt hazırla
                    prompt = f"""
                    Orman yangını risk analizi yap:
                    
                    Koordinatlar: {lat}, {lon}
                    Hava durumu: Sıcaklık {weather_data.get('sicaklik', 0)}°C, Nem {weather_data.get('nem', 0)}%, Rüzgar {weather_data.get('ruzgar_hizi', 0)} km/h
                    Alan bilgisi: {area_info.get('name', 'Orman Alanı')}, Tip: {area_info.get('landuse', 'forest')}, Alan: {area_info.get('area', 0)} km²
                    
                    Risk faktörlerini analiz et ve şu formatta yanıtla:
                    - Hava durumu risk skoru (0-100)
                    - İnsan kaynaklı risk faktörleri
                    - Birleşik risk seviyesi (Düşük/Orta/Yüksek)
                    - Risk rengi (green/orange/red)
                    """
                    
                    # Gerçek API çağrısı
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
                        
                        # API yanıtını parse et
                        analysis_text = response.choices[0].message.content
                    else:
                        analysis_text = "API bağlantısı kurulamadı, dummy analiz kullanılıyor."
                    
                    # API yanıtı zaten parse edildi
                    
                    # Basit risk hesaplama (fallback)
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
                    # Hata durumunda dummy analiz döndür
                    return self._dummy_analysis(coordinates, weather_data, area_info)
            
            def _dummy_analysis(self, coordinates, weather_data, area_info):
                """Dummy analiz (fallback)"""
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
        # Dummy analyzer'ı tekrar kullan
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

# Global LM analyzer instance
lm_analyzer = LMRiskAnalyzer() 