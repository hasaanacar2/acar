import threading
import schedule
import time
import json
import requests
from datetime import datetime
import os
import logging
import random
from lm_risk_analyzer import lm_analyzer

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_updater.log'),
        logging.StreamHandler()
    ]
)

# WeatherAPI.com API anahtarı - Environment variable'dan oku
WEATHERAPI_KEY = os.environ.get('WEATHERAPI_KEY')
if not WEATHERAPI_KEY:
    raise RuntimeError('WEATHERAPI_KEY environment variable tanımlı değil!')

class AutoUpdater:
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.last_update = None
        
    def get_test_weather_data(self, lat, lon):
        """
        Test amaçlı koordinat bazlı hava durumu verileri üretir
        """
        # Koordinat bazlı gerçekçi test verileri
        # Enlem (lat) etkisi: Güney daha sıcak
        lat_factor = (lat - 35) / 10  # Türkiye için normalize
        
        # Boylam (lon) etkisi: Doğu daha kuru
        lon_factor = (lon - 26) / 15  # Türkiye için normalize
        
        # Koordinat bazlı sıcaklık hesaplama
        base_temp = 25 + (lat_factor * 5) + (lon_factor * 2)
        sicaklik = max(10, min(40, base_temp + random.uniform(-5, 5)))
        
        # Koordinat bazlı nem hesaplama
        base_humidity = 60 - (lat_factor * 10) + (lon_factor * 5)
        nem = max(20, min(90, base_humidity + random.uniform(-10, 10)))
        
        # Koordinat bazlı rüzgar hesaplama
        base_wind = 15 + (lon_factor * 5)
        ruzgar_hizi = max(0, min(50, base_wind + random.uniform(-5, 5)))
        
        # Koordinat bazlı yağış hesaplama
        base_rain = max(0, 20 - (lat_factor * 10) - (lon_factor * 5))
        yagis_7_gun = max(0, min(100, base_rain + random.uniform(-10, 10)))
        
        weather_info = {
            'sicaklik': round(sicaklik, 1),
            'nem': round(nem, 1),
            'ruzgar_hizi': round(ruzgar_hizi, 1),
            'yagis_7_gun': round(yagis_7_gun, 1)
        }
        return weather_info, None

    def get_weather_data_for_coordinates(self, lat, lon):
        """
        Belirli koordinatlar için WeatherAPI.com'dan hava durumu verilerini çeker
        """
        try:
            # WeatherAPI.com çağrısı - Koordinat bazlı veri
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': WEATHERAPI_KEY,
                'q': f"{lat},{lon}",
                'aqi': 'no'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                error_data = response.json()
                logging.warning(f"WeatherAPI Hatası ({response.status_code}): {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}")
                return None, f"WeatherAPI Hatası: {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}"
            
            data = response.json()
            current = data['current']
            
            # WeatherAPI.com verilerini topla
            weather_info = {
                'sicaklik': current['temp_c'],
                'nem': current['humidity'],
                'ruzgar_hizi': current['wind_kph'],  # Zaten km/h cinsinden
                'yagis_7_gun': current.get('precip_mm', 0)  # Mevcut yağış verisi
            }
            
            return weather_info, None
            
        except requests.exceptions.Timeout:
            logging.warning(f"API timeout: {lat}, {lon}")
            return None, f"API timeout: {lat}, {lon}"
        except requests.exceptions.RequestException as e:
            logging.error(f"API bağlantı hatası: {str(e)}")
            return None, f"API bağlantı hatası: {str(e)}"
        except Exception as e:
            logging.error(f"Veri çekme hatası: {str(e)}")
            return None, f"Veri çekme hatası: {str(e)}"

    def hesapla_risk_skoru(self, sicaklik, nem, ruzgar_hizi, yagis_7_gun):
        """
        Orman yangını risk skoru hesaplama fonksiyonu
        """
        risk_skoru = 0
        
        # Sıcaklık faktörü (0-30 puan)
        if sicaklik >= 30:
            risk_skoru += 30
        elif sicaklik >= 25:
            risk_skoru += 25
        elif sicaklik >= 20:
            risk_skoru += 20
        elif sicaklik >= 15:
            risk_skoru += 15
        elif sicaklik >= 10:
            risk_skoru += 10
        else:
            risk_skoru += 5
        
        # Nem faktörü (0-25 puan)
        if nem <= 30:
            risk_skoru += 25
        elif nem <= 40:
            risk_skoru += 20
        elif nem <= 50:
            risk_skoru += 15
        elif nem <= 60:
            risk_skoru += 10
        elif nem <= 70:
            risk_skoru += 5
        else:
            risk_skoru += 0
        
        # Rüzgar hızı faktörü (0-25 puan)
        if ruzgar_hizi >= 50:
            risk_skoru += 25
        elif ruzgar_hizi >= 40:
            risk_skoru += 20
        elif ruzgar_hizi >= 30:
            risk_skoru += 15
        elif ruzgar_hizi >= 20:
            risk_skoru += 10
        elif ruzgar_hizi >= 10:
            risk_skoru += 5
        else:
            risk_skoru += 0
        
        # Yağış faktörü (0-20 puan)
        if yagis_7_gun <= 5:
            risk_skoru += 20
        elif yagis_7_gun <= 10:
            risk_skoru += 15
        elif yagis_7_gun <= 20:
            risk_skoru += 10
        elif yagis_7_gun <= 30:
            risk_skoru += 5
        else:
            risk_skoru += 0
        
        return min(risk_skoru, 100)

    def get_risk_level(self, risk_skoru):
        """
        Risk skoruna göre seviye belirleme
        """
        if risk_skoru >= 70:
            return "Yüksek"
        elif risk_skoru >= 40:
            return "Orta"
        else:
            return "Düşük"

    def calculate_centroid(self, coordinates):
        """
        Poligon koordinatlarından merkez nokta hesaplama
        """
        if not coordinates or len(coordinates) == 0:
            return None, None
        
        # İlk ring'i al (polygon'un dış sınırı)
        ring = coordinates[0]
        
        if len(ring) < 3:
            return None, None
        
        # Basit centroid hesaplama
        lat_sum = sum(point[1] for point in ring)
        lon_sum = sum(point[0] for point in ring)
        
        centroid_lat = lat_sum / len(ring)
        centroid_lon = lon_sum / len(ring)
        
        return centroid_lat, centroid_lon

    def update_forest_risks(self):
        """
        Tüm orman alanlarının risk verilerini günceller
        """
        try:
            logging.info("Orman risk güncellemesi başlatılıyor...")
            
            # GeoJSON dosyasını oku - bölünmüş dosyayı kullan
            geojson_path = 'static/export_improved.geojson'
            if not os.path.exists(geojson_path):
                logging.error(f"GeoJSON dosyası bulunamadı: {geojson_path}")
                return
            
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            
            logging.info(f"Toplam {len(geojson_data['features'])} alan güncellenecek.")
            
            # Her feature için risk hesapla
            for i, feature in enumerate(geojson_data['features']):
                if i % 100 == 0:
                    logging.info(f"İşleniyor: {i+1}/{len(geojson_data['features'])}")
                
                # Centroid doğrudan properties'ten alınıyor
                properties = feature.get('properties', {})
                centroid_lat = properties.get('centroid_lat')
                centroid_lon = properties.get('centroid_lon')
                
                if centroid_lat is None or centroid_lon is None:
                    # Geriye dönük uyumluluk için centroid hesapla
                    geometry = feature['geometry']
                    if geometry['type'] == 'Polygon':
                        coordinates = geometry['coordinates']
                    elif geometry['type'] == 'MultiPolygon':
                        coordinates = geometry['coordinates'][0]
                    else:
                        continue
                    centroid_lat, centroid_lon = self.calculate_centroid(coordinates)
                
                if centroid_lat is None or centroid_lon is None:
                    continue
                
                # Hava durumu verilerini çek
                weather_data, error = self.get_weather_data_for_coordinates(centroid_lat, centroid_lon)
                
                if error or weather_data is None:
                    logging.warning(f"Feature {i}: {error}")
                    # Hata durumunda bu alanı atla
                    continue
                else:
                    # Temel risk hesapla
                    risk_skoru = self.hesapla_risk_skoru(
                        weather_data.get('sicaklik', 25),
                        weather_data.get('nem', 50),
                        weather_data.get('ruzgar_hizi', 15),
                        weather_data.get('yagis_7_gun', 10)
                    )
                    risk_seviyesi = self.get_risk_level(risk_skoru)
                    
                    # Bunun yerine, her zaman aşağıdaki varsayılanları yaz:
                    feature['properties']['human_risk_score'] = 50
                    feature['properties']['human_risk_factors'] = [
                        {"factor": "Yerleşim yakınlığı", "score": 50, "description": "Orta seviye risk"},
                        {"factor": "Turizm aktiviteleri", "score": 40, "description": "Düşük-orta risk"},
                        {"factor": "Yol ağı", "score": 60, "description": "Orta-yüksek risk"}
                    ]
                    feature['properties']['lm_analysis'] = "LM analizi sadece harita üzerinde tıklanan alanlar için yapılır."
                    feature['properties']['weather_weight'] = 60.0
                    feature['properties']['human_weight'] = 40.0
                    feature['properties']['distance_from_city'] = 50.0
                    feature['properties']['nearest_city'] = "bilinmiyor"
                
                # Properties'e risk bilgilerini ekle
                if 'properties' not in feature:
                    feature['properties'] = {}
                
                feature['properties']['risk_skoru'] = risk_skoru
                feature['properties']['risk_seviyesi'] = risk_seviyesi
                
                # Weather data varsa ekle, yoksa varsayılan değerler
                if weather_data is not None:
                    feature['properties']['sicaklik'] = weather_data.get('sicaklik', 0)
                    feature['properties']['nem'] = weather_data.get('nem', 0)
                    feature['properties']['ruzgar_hizi'] = weather_data.get('ruzgar_hizi', 0)
                    feature['properties']['yagis_7_gun'] = weather_data.get('yagis_7_gun', 0)
                else:
                    feature['properties']['sicaklik'] = 0
                    feature['properties']['nem'] = 0
                    feature['properties']['ruzgar_hizi'] = 0
                    feature['properties']['yagis_7_gun'] = 0
                
                feature['properties']['son_guncelleme'] = datetime.now().isoformat()
                
                # API rate limit için bekle (test verileri için daha hızlı)
                time.sleep(0.01)
            
            # Güncellenmiş GeoJSON'u kaydet
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f'static/export_with_risk_auto_{timestamp}.geojson'
            
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(geojson_data, f, ensure_ascii=False, indent=2)
                
                # JSON dosyasının geçerli olduğunu kontrol et
                with open(output_filename, 'r', encoding='utf-8') as f:
                    json.load(f)
                
                # En son güncellenmiş dosyayı işaretle
                latest_file = 'static/export_with_risk_latest.geojson'
                with open(latest_file, 'w', encoding='utf-8') as f:
                    json.dump(geojson_data, f, ensure_ascii=False, indent=2)
                
                logging.info(f"Risk güncellemesi tamamlandı. Sonuç: {output_filename}")
                
            except Exception as e:
                logging.error(f"JSON kaydetme hatası: {str(e)}")
                # Hata durumunda dosyayı sil
                if os.path.exists(output_filename):
                    os.remove(output_filename)
                raise
            
            self.last_update = datetime.now()
            logging.info(f"Risk güncellemesi tamamlandı. Sonuç: {output_filename}")
            
        except Exception as e:
            logging.error(f"Risk güncellemesi sırasında hata: {str(e)}")

    def update_forest_lm_risks(self):
        """
        Tüm orman alanlarının LM destekli birleşik risk verilerini günceller
        """
        try:
            logging.info("Birleşik LM risk güncellemesi başlatılıyor...")
            geojson_path = 'static/export_improved.geojson'
            fires_path = 'static/fires.json'
            fire_points = []
            if os.path.exists(fires_path):
                with open(fires_path, 'r', encoding='utf-8') as f:
                    fire_points = json.load(f)
            if not os.path.exists(geojson_path):
                logging.error(f"GeoJSON dosyası bulunamadı: {geojson_path}")
                return
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            for i, feature in enumerate(geojson_data['features']):
                properties = feature.get('properties', {})
                centroid_lat = properties.get('centroid_lat')
                centroid_lon = properties.get('centroid_lon')
                area = properties.get('area', 0)
                landuse = properties.get('landuse', 'forest')
                name = properties.get('name', 'Orman Alanı')
                area_info = {'landuse': landuse, 'area': area, 'name': name}
                if centroid_lat is None or centroid_lon is None:
                    geometry = feature['geometry']
                    if geometry['type'] == 'Polygon':
                        coordinates = geometry['coordinates']
                    elif geometry['type'] == 'MultiPolygon':
                        coordinates = geometry['coordinates'][0]
                    else:
                        continue
                    centroid_lat, centroid_lon = self.calculate_centroid(coordinates)
                if centroid_lat is None or centroid_lon is None:
                    continue
                # Hava durumu verisini çek
                weather_data, error = self.get_weather_data_for_coordinates(centroid_lat, centroid_lon)
                if error or weather_data is None:
                    continue
                # LM analizli birleşik risk hesapla (yangın noktalarını da ilet)
                combined_risk = lm_analyzer.analyze_forest_area((centroid_lat, centroid_lon), weather_data, area_info, fire_points)
                # Sonuçları properties'e yaz
                for k, v in combined_risk.items():
                    feature['properties'][k] = v
                feature['properties']['son_guncelleme'] = datetime.now().isoformat()
                time.sleep(0.2)  # LM API rate limit için bekle
            # Kaydet
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f'static/export_with_lm_risk_{timestamp}.geojson'
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)
            with open('static/export_with_lm_risk_latest.geojson', 'w', encoding='utf-8') as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)
            logging.info(f"Birleşik LM risk güncellemesi tamamlandı. Sonuç: {output_filename}")
        except Exception as e:
            logging.error(f"Birleşik LM risk güncellemesi sırasında hata: {str(e)}")

    def start_scheduler(self):
        """
        Zamanlayıcıyı başlatır
        """
        schedule.every().day.at("00:00").do(self.update_forest_lm_risks)
        schedule.every().day.at("12:00").do(self.update_forest_lm_risks)
        schedule.every().day.at("12:00").do(self.update_forest_risks)
        logging.info("Zamanlayıcı başlatıldı. Her gün saat 00:00 ve 12:00'de LM risk güncellemesi, 12:00'de klasik risk güncellemesi yapılacak.")
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)

    def start(self):
        """
        Background thread'i başlatır
        """
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self.start_scheduler, daemon=True)
            self.thread.start()
            logging.info("Auto updater başlatıldı.")

    def stop(self):
        """
        Background thread'i durdurur
        """
        self.is_running = False
        logging.info("Auto updater durduruldu.")

# Global auto updater instance
auto_updater = AutoUpdater() 