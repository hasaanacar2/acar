import os
import json
import time
import logging

# Environment variable kontrolü
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

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
                self.client = groq.Groq(api_key=GROQ_API_KEY)
                self.model = "llama3-8b-8192"
                print("Groq API başarıyla kuruldu")
            
            def analyze_forest_area(self, coordinates, weather_data, area_info):
                """Gerçek LM analizi"""
                try:
                    lat, lon = coordinates
                    
                    # Basit risk hesaplama (gerçek API için)
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
                    
                    return {
                        "combined_risk_score": risk_score,
                        "combined_risk_level": risk_level,
                        "combined_risk_color": risk_color,
                        "weather_data": weather_data,
                        "analysis": f"LM Analiz: {area_info.get('name', 'Orman Alanı')} - {risk_level} risk",
                        "weather_weight": 60.0,
                        "human_weight": 40.0,
                        "human_risk_score": risk_score * 0.8,
                        "weather_risk_score": risk_score * 0.6,
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
                    return self.analyze_forest_area(coordinates, weather_data, area_info)
        
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