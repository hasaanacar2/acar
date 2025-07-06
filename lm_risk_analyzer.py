import groq
import json
import requests
from datetime import datetime
import logging
import math
import time
import os

# Groq API anahtarı - environment variable'dan oku
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
if not GROQ_API_KEY:
    raise RuntimeError('GROQ_API_KEY environment variable tanımlı değil!')

class LMRiskAnalyzer:
    def __init__(self):
        self.client = None
        self.model = None
        self.setup_groq()
        
    def setup_groq(self):
        """
        Groq modelini kurar
        """
        try:
            self.client = groq.Groq(api_key=GROQ_API_KEY)
            # Groq'da kullanılabilir hızlı model: llama3-8b-8192
            self.model = "llama3-8b-8192"
            logging.info("Groq Llama3-8b-8192 modeli başarıyla kuruldu")
        except Exception as e:
            logging.error(f"Groq kurulum hatası: {str(e)}")
            self.client = None
    
    def analyze_human_fire_risk(self, coordinates, area_info):
        """
        Koordinatlar ve alan bilgilerine dayalı insan kaynaklı yangın riskini analiz eder
        """
        if not self.client:
            return {"human_risk_score": 50, "human_risk_factors": ["Model kurulamadı"]}
        
        # Rate limiting - quota aşımını önlemek için
        time.sleep(0.2)  # 0.2 saniye bekle - Groq çok hızlı
        
        try:
            # Alan bilgilerini hazırla
            lat, lon = coordinates
            area_type = area_info.get('landuse', 'forest')
            area_size = area_info.get('area', 0)
            fire_status = area_info.get('fire_status', 'none')
            fire_spread_risk = area_info.get('fire_spread_risk', False)
            nearest_fire_dist = area_info.get('nearest_fire_dist', None)
            nearest_fire_status = area_info.get('nearest_fire_status', None)
            
            # Groq'ya gönderilecek prompt - Türkçe yanıt için
            prompt = f"""
            Türkiye'deki orman yangını risk analizi yapıyorum. 
            
            Koordinatlar: {lat}, {lon}
            Alan tipi: {area_type}
            Alan büyüklüğü: {area_size}
            
            Bu alanın yangın durumu: {fire_status}
            Bu alanın yakınında aktif yangın yayılma riski: {fire_spread_risk}
            En yakın yangın mesafesi: {nearest_fire_dist} km, durumu: {nearest_fire_status}
            
            Bu koordinatlar için insan kaynaklı yangın risk faktörlerini analiz et:
            1. Yerleşim alanlarına yakınlık
            2. Turizm aktiviteleri
            3. Tarım alanlarına yakınlık
            4. Yol ağına yakınlık
            5. Endüstriyel aktiviteler
            6. Kamp alanları ve piknik yerleri
            7. Elektrik hatları
            8. İnsan trafiği yoğunluğu
            
            Eğer bu alanın içinde veya yakınında aktif yangın varsa, yangın riski ve yayılma riskini özellikle değerlendir.
            Her faktör için 0-100 arası risk skoru ver ve toplam insan kaynaklı risk skorunu hesapla.
            
            Lütfen yanıtı Türkçe olarak JSON formatında ver:
            {{
                "human_risk_score": 0-100 arası toplam skor,
                "human_risk_factors": [
                    {{"factor": "faktör adı", "score": 0-100, "description": "açıklama"}}
                ],
                "analysis": "Türkçe genel analiz metni (özellikle yangın ve yayılma riski varsa belirt)"
            }}
            
            Önemli: Yanıtı mutlaka Türkçe olarak ver ve JSON formatında yaz.
            """
            
            # Groq API çağrısı
            if self.model:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=1024,
                    temperature=0.7
                )
                
                response_text = response.choices[0].message.content
            else:
                raise Exception("Model kurulamadı")
            
            # JSON yanıtını parse et
            try:
                # Yanıtın JSON kısmını bul
                if response_text:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        json_str = response_text[start_idx:end_idx]
                        result = json.loads(json_str)
                        return result
                else:
                    # JSON bulunamazsa varsayılan değerler
                    return {
                        "human_risk_score": 50,
                        "human_risk_factors": [
                            {"factor": "Yerleşim yakınlığı", "score": 50, "description": "Orta seviye risk"},
                            {"factor": "Turizm aktiviteleri", "score": 40, "description": "Düşük-orta risk"},
                            {"factor": "Yol ağı", "score": 60, "description": "Orta-yüksek risk"}
                        ],
                        "analysis": "İnsan kaynaklı risk faktörleri analiz edildi."
                    }
            except json.JSONDecodeError:
                # JSON parse edilemezse varsayılan değerler
                return {
                    "human_risk_score": 50,
                    "human_risk_factors": [
                        {"factor": "Yerleşim yakınlığı", "score": 50, "description": "Orta seviye risk"},
                        {"factor": "Turizm aktiviteleri", "score": 40, "description": "Düşük-orta risk"},
                        {"factor": "Yol ağı", "score": 60, "description": "Orta-yüksek risk"}
                    ],
                    "analysis": "İnsan kaynaklı risk faktörleri analiz edildi."
                }
                
        except Exception as e:
            logging.error(f"Groq analiz hatası: {str(e)}")
            return {
                "human_risk_score": 50,
                "human_risk_factors": [{"factor": "Analiz hatası", "score": 50, "description": str(e)}],
                "analysis": "Groq analizi başarısız oldu."
            }
    
    def calculate_distance_from_city_center(self, coordinates):
        """
        Koordinatların en yakın büyük şehir merkezine olan uzaklığını hesaplar
        """
        lat, lon = coordinates
        
        # Türkiye'nin büyük şehir merkezleri ve koordinatları
        city_centers = {
            'istanbul': (41.0082, 28.9784),
            'ankara': (39.9334, 32.8597),
            'izmir': (38.4192, 27.1287),
            'bursa': (40.1885, 29.0610),
            'antalya': (36.8969, 30.7133),
            'adana': (37.0000, 35.3213),
            'konya': (37.8667, 32.4833),
            'gaziantep': (37.0662, 37.3833),
            'kayseri': (38.7205, 35.4826),
            'mersin': (36.8000, 34.6333),
            'diyarbakir': (37.9144, 40.2306),
            'samsun': (41.2867, 36.3300),
            'denizli': (37.7765, 29.0864),
            'eskisehir': (39.7767, 30.5206),
            'urfa': (37.1591, 38.7969),
            'malatya': (38.3552, 38.3095),
            'erzurum': (39.9000, 41.2700),
            'van': (38.4891, 43.4089),
            'batman': (37.8812, 41.1351),
            'elazig': (38.6810, 39.2264)
        }
        
        # En yakın şehir merkezini bul
        min_distance = float('inf')
        nearest_city = None
        
        for city_name, city_coords in city_centers.items():
            # Haversine formülü ile mesafe hesapla
            lat1, lon1 = lat, lon
            lat2, lon2 = city_coords
            
            # Radyana çevir
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            
            # Haversine formülü
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            distance = 6371 * c  # Dünya yarıçapı (km)
            
            if distance < min_distance:
                min_distance = distance
                nearest_city = city_name
        
        return min_distance, nearest_city
    
    def calculate_dynamic_weights(self, coordinates, area_info):
        """
        Koordinatlara ve alan bilgilerine göre dinamik ağırlık hesaplar
        """
        lat, lon = coordinates
        area_type = area_info.get('landuse', 'forest')
        area_size = area_info.get('area', 0)
        
        # Şehir merkezine uzaklığı hesapla
        distance_from_city, nearest_city = self.calculate_distance_from_city_center(coordinates)
        
        # Alan tipine göre temel ağırlık
        if area_type == 'forest':
            base_human_weight = 0.30  # Orman alanları için %30 insan faktörü
        elif area_type == 'agricultural':
            base_human_weight = 0.50  # Tarım alanları için %50 insan faktörü
        elif area_type == 'urban':
            base_human_weight = 0.70  # Şehir alanları için %70 insan faktörü
        else:
            base_human_weight = 0.40  # Varsayılan %40
        
        # Mesafe bazlı ağırlık ayarlaması
        if distance_from_city <= 5:  # 5 km içinde
            distance_factor = 1.5  # İnsan faktörünü artır
        elif distance_from_city <= 15:  # 5-15 km
            distance_factor = 1.2
        elif distance_from_city <= 30:  # 15-30 km
            distance_factor = 1.0
        elif distance_from_city <= 50:  # 30-50 km
            distance_factor = 0.8
        elif distance_from_city <= 100:  # 50-100 km
            distance_factor = 0.6
        else:  # 100+ km
            distance_factor = 0.4  # İnsan faktörünü azalt
        
        # Alan büyüklüğüne göre ayarlama
        if area_size > 1000:  # Büyük alanlar
            size_factor = 0.8  # İnsan faktörünü azalt
        elif area_size > 100:  # Orta alanlar
            size_factor = 1.0
        else:  # Küçük alanlar
            size_factor = 1.2  # İnsan faktörünü artır
        
        # Dinamik insan ağırlığı hesapla
        human_weight = base_human_weight * distance_factor * size_factor
        human_weight = max(0.1, min(0.8, human_weight))  # %10-%80 arası sınırla
        
        weather_weight = 1.0 - human_weight
        
        return weather_weight, human_weight
    
    def combine_risks(self, weather_risk, human_risk, coordinates, area_info):
        """
        Hava durumu ve insan kaynaklı riskleri dinamik ağırlıklarla birleştirir
        """
        weather_score = weather_risk.get('risk_skoru', 50)
        human_score = human_risk.get('human_risk_score', 50)
        
        # Dinamik ağırlıkları hesapla
        weather_weight, human_weight = self.calculate_dynamic_weights(coordinates, area_info)
        
        # Dinamik ağırlıklı ortalama
        combined_score = (weather_score * weather_weight) + (human_score * human_weight)
        
        # Risk seviyesi belirleme
        if combined_score >= 70:
            risk_level = "Yüksek"
            color = "red"
        elif combined_score >= 40:
            risk_level = "Orta"
            color = "orange"
        else:
            risk_level = "Düşük"
            color = "green"
        
        # Şehir merkezine uzaklığı hesapla
        distance_from_city, nearest_city = self.calculate_distance_from_city_center(coordinates)
        
        return {
            "combined_risk_score": round(combined_score, 1),
            "combined_risk_level": risk_level,
            "combined_risk_color": color,
            "weather_risk_score": weather_score,
            "human_risk_score": human_score,
            "weather_weight": round(weather_weight * 100, 1),
            "human_weight": round(human_weight * 100, 1),
            "distance_from_city": round(distance_from_city, 1),
            "nearest_city": nearest_city,
            "weather_data": weather_risk,
            "human_risk_factors": human_risk.get('human_risk_factors', []),
            "analysis": human_risk.get('analysis', ''),
            "area_type": area_info.get('landuse', 'forest'),
            "area_size": area_info.get('area', 0)
        }
    
    def analyze_forest_area(self, coordinates, weather_data, area_info, fire_points=None):
        """
        Bir orman alanı için tam risk analizi yapar. fire_points: [{'lat':..., 'lon':..., 'status':...}, ...]
        """
        lat, lon = coordinates
        # Yangın noktası var mı?
        fire_status = "none"
        fire_spread_risk = False
        nearest_fire_dist = None
        nearest_fire_status = None
        if fire_points:
            for fire in fire_points:
                dist = self._haversine(lat, lon, fire['lat'], fire['lon'])
                if nearest_fire_dist is None or dist < nearest_fire_dist:
                    nearest_fire_dist = dist
                    nearest_fire_status = fire['status']
                if dist < 2.0 and fire['status'] == 'active':
                    fire_status = "active"
                elif dist < 2.0 and fire['status'] == 'extinguished' and fire_status != "active":
                    fire_status = "extinguished"
                # 2-10 km arası aktif yangın varsa yayılma riski
                if 2.0 <= dist < 10.0 and fire['status'] == 'active':
                    fire_spread_risk = True
        # Hava durumu riskini hesapla
        from auto_updater import AutoUpdater
        temp_updater = AutoUpdater()
        risk_skoru = temp_updater.hesapla_risk_skoru(
            weather_data.get('sicaklik', 25),
            weather_data.get('nem', 50),
            weather_data.get('ruzgar_hizi', 15),
            weather_data.get('yagis_7_gun', 10)
        )
        risk_seviyesi = temp_updater.get_risk_level(risk_skoru)
        weather_risk = {
            'risk_skoru': risk_skoru,
            'risk_seviyesi': risk_seviyesi,
            'sicaklik': weather_data.get('sicaklik', 25),
            'nem': weather_data.get('nem', 50),
            'ruzgar_hizi': weather_data.get('ruzgar_hizi', 15),
            'yagis_7_gun': weather_data.get('yagis_7_gun', 10)
        }
        # İnsan kaynaklı riski analiz et (prompt'a yangın durumu ekle)
        area_info = dict(area_info)
        area_info['fire_status'] = fire_status
        area_info['fire_spread_risk'] = fire_spread_risk
        area_info['nearest_fire_dist'] = nearest_fire_dist
        area_info['nearest_fire_status'] = nearest_fire_status
        human_risk = self.analyze_human_fire_risk(coordinates, area_info)
        # Riskleri dinamik ağırlıklarla birleştir
        combined_risk = self.combine_risks(weather_risk, human_risk, coordinates, area_info)
        combined_risk['fire_status'] = fire_status
        combined_risk['fire_spread_risk'] = fire_spread_risk
        combined_risk['nearest_fire_dist'] = nearest_fire_dist
        combined_risk['nearest_fire_status'] = nearest_fire_status
        return combined_risk
    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

# Global LM analyzer instance
lm_analyzer = LMRiskAnalyzer() 