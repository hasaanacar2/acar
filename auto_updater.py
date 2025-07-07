import threading
import schedule
import time
import json
import requests
from datetime import datetime, timedelta
import os
import logging
import random
import concurrent.futures
from collections import deque
from lm_risk_analyzer import lm_analyzer, get_cached_analysis, update_weather_date
from cache_manager import cache_manager

# WeatherAPI rate limiting
weather_request_times = deque()
weather_rate_limit_lock = threading.Lock()
WEATHER_MAX_REQUESTS_PER_MINUTE = 50  # WeatherAPI için güvenli limit
WEATHER_RATE_LIMIT_WINDOW = 60

def check_weather_rate_limit():
    """
    WeatherAPI rate limit kontrolü - dakikada maksimum 50 istek
    """
    with weather_rate_limit_lock:
        now = time.time()
        
        # 60 saniyeden eski istekleri temizle
        while weather_request_times and now - weather_request_times[0] > WEATHER_RATE_LIMIT_WINDOW:
            weather_request_times.popleft()
        
        # Rate limit kontrolü
        if len(weather_request_times) >= WEATHER_MAX_REQUESTS_PER_MINUTE:
            # En eski istekten sonraki süreyi bekle
            wait_time = WEATHER_RATE_LIMIT_WINDOW - (now - weather_request_times[0])
            if wait_time > 0:
                logging.warning(f"WeatherAPI rate limit aşıldı, {wait_time:.2f} saniye bekleniyor...")
                time.sleep(wait_time)
                return check_weather_rate_limit()  # Tekrar kontrol et
        
        # Yeni istek zamanını ekle
        weather_request_times.append(now)
        return True

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

# Performans optimizasyonu için global değişkenler
weather_cache = {}  # Hava durumu cache'i
weather_cache_lock = threading.Lock()
MAX_WORKERS = 4  # Paralel işlem sayısı

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
        Sunucu başlatıldığında 1 gün önceki 12:00'ın verilerini alır
        Performans için cache kullanır
        """
        # Cache key oluştur
        cache_key = f"{lat:.4f}_{lon:.4f}"
        
        # Cache'den kontrol et
        with weather_cache_lock:
            if cache_key in weather_cache:
                cache_time, weather_data = weather_cache[cache_key]
                # Cache 1 saat geçerli
                if time.time() - cache_time < 3600:
                    return weather_data, None
        
        try:
            # Rate limit kontrolü
            check_weather_rate_limit()
            
            # 1 gün önceki 12:00'ı hesapla
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_noon = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)
            weather_date = yesterday_noon.strftime('%Y-%m-%d')
            
            # Yeni hava durumu tarihi kontrolü
            if update_weather_date(weather_date):
                logging.info(f"🔄 Yeni hava durumu verisi tespit edildi: {weather_date}")
            
            # WeatherAPI.com çağrısı - Geçmiş veri için
            url = "http://api.weatherapi.com/v1/history.json"
            params = {
                'key': WEATHERAPI_KEY,
                'q': f"{lat},{lon}",
                'dt': weather_date,
                'aqi': 'no'
            }
            
            response = requests.get(url, params=params, timeout=5)  # Timeout azaltıldı
            
            if response.status_code != 200:
                error_data = response.json()
                logging.warning(f"WeatherAPI Hatası ({response.status_code}): {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}")
                # Hata durumunda mevcut veriyi kullan
                return self.get_current_weather_data(lat, lon)
            
            data = response.json()
            
            # Geçmiş veri varsa kullan, yoksa mevcut veriyi al
            if 'forecast' in data and 'forecastday' in data['forecast'] and len(data['forecast']['forecastday']) > 0:
                forecast_day = data['forecast']['forecastday'][0]
                hour_data = forecast_day['hour'][12]  # 12:00 verisi
                
                weather_info = {
                    'sicaklik': hour_data['temp_c'],
                    'nem': hour_data['humidity'],
                    'ruzgar_hizi': hour_data['wind_kph'],
                    'yagis_7_gun': hour_data.get('precip_mm', 0)
                }
                
                # Cache'e kaydet
                with weather_cache_lock:
                    weather_cache[cache_key] = (time.time(), weather_info)
                
                logging.info(f"1 gün önceki 12:00 verisi kullanıldı: {lat}, {lon}")
                return weather_info, None
            else:
                # Geçmiş veri yoksa mevcut veriyi al
                return self.get_current_weather_data(lat, lon)
                
        except requests.exceptions.Timeout:
            logging.warning(f"API timeout: {lat}, {lon}")
            return self.get_current_weather_data(lat, lon)
        except requests.exceptions.RequestException as e:
            logging.error(f"API bağlantı hatası: {str(e)}")
            return self.get_current_weather_data(lat, lon)
        except Exception as e:
            logging.error(f"Veri çekme hatası: {str(e)}")
            return self.get_current_weather_data(lat, lon)

    def get_current_weather_data(self, lat, lon):
        """
        Mevcut hava durumu verilerini çeker (fallback için)
        """
        try:
            # Rate limit kontrolü
            check_weather_rate_limit()
            
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': WEATHERAPI_KEY,
                'q': f"{lat},{lon}",
                'aqi': 'no'
            }
            
            response = requests.get(url, params=params, timeout=5)  # Timeout azaltıldı
            
            if response.status_code != 200:
                error_data = response.json()
                logging.warning(f"WeatherAPI Mevcut Veri Hatası ({response.status_code}): {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}")
                return None, f"WeatherAPI Hatası: {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}"
            
            data = response.json()
            current = data['current']
            
            weather_info = {
                'sicaklik': current['temp_c'],
                'nem': current['humidity'],
                'ruzgar_hizi': current['wind_kph'],
                'yagis_7_gun': current.get('precip_mm', 0)
            }
            
            return weather_info, None
            
        except Exception as e:
            logging.error(f"Mevcut veri çekme hatası: {str(e)}")
            return None, f"Veri çekme hatası: {str(e)}"

    def hesapla_risk_skoru(self, sicaklik, nem, ruzgar_hizi, yagis_7_gun):
        """
        Geliştirilmiş orman yangını risk skoru hesaplama fonksiyonu
        """
        risk_skoru = 0
        
        # Sıcaklık faktörü (0-35 puan) - Daha hassas
        if sicaklik >= 35:
            risk_skoru += 35
        elif sicaklik >= 30:
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
        
        # Nem faktörü (0-30 puan) - Daha hassas
        if nem <= 25:
            risk_skoru += 30
        elif nem <= 35:
            risk_skoru += 25
        elif nem <= 45:
            risk_skoru += 20
        elif nem <= 55:
            risk_skoru += 15
        elif nem <= 65:
            risk_skoru += 10
        elif nem <= 75:
            risk_skoru += 5
        else:
            risk_skoru += 0
        
        # Rüzgar hızı faktörü (0-25 puan) - Daha hassas
        if ruzgar_hizi >= 40:
            risk_skoru += 25
        elif ruzgar_hizi >= 30:
            risk_skoru += 20
        elif ruzgar_hizi >= 20:
            risk_skoru += 15
        elif ruzgar_hizi >= 15:
            risk_skoru += 10
        elif ruzgar_hizi >= 10:
            risk_skoru += 5
        else:
            risk_skoru += 0
        
        # Yağış faktörü (0-20 puan) - Daha hassas
        if yagis_7_gun <= 3:
            risk_skoru += 20
        elif yagis_7_gun <= 8:
            risk_skoru += 15
        elif yagis_7_gun <= 15:
            risk_skoru += 10
        elif yagis_7_gun <= 25:
            risk_skoru += 5
        else:
            risk_skoru += 0
        
        # Mevsim faktörü (0-10 puan) - Yaz aylarında ek risk
        import datetime
        current_month = datetime.datetime.now().month
        if current_month in [6, 7, 8]:  # Haziran, Temmuz, Ağustos
            risk_skoru += 10
        elif current_month in [5, 9]:  # Mayıs, Eylül
            risk_skoru += 5
        
        # Minimum risk skoru (çok düşük skorları engelle)
        risk_skoru = max(risk_skoru, 15)
        
        return min(risk_skoru, 100)

    def get_risk_level(self, risk_skoru):
        """
        Geliştirilmiş risk skoruna göre seviye belirleme
        """
        if risk_skoru >= 75:
            return "Çok Yüksek"
        elif risk_skoru >= 60:
            return "Yüksek"
        elif risk_skoru >= 45:
            return "Orta-Yüksek"
        elif risk_skoru >= 30:
            return "Orta"
        elif risk_skoru >= 20:
            return "Düşük-Orta"
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

    def process_single_feature(self, feature_data):
        """
        Tek bir feature'ı işler (paralel işlem için)
        """
        try:
            i, feature = feature_data
            
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
                    return None
                centroid_lat, centroid_lon = self.calculate_centroid(coordinates)
            
            if centroid_lat is None or centroid_lon is None:
                return None
            
            # Hava durumu verilerini çek
            weather_data, error = self.get_weather_data_for_coordinates(centroid_lat, centroid_lon)
            
            if error or weather_data is None:
                logging.warning(f"Feature {i}: {error}")
                # Hata durumunda bu alanı atla
                return None
            else:
                # Temel risk hesapla
                risk_skoru = self.hesapla_risk_skoru(
                    weather_data.get('sicaklik', 25),
                    weather_data.get('nem', 50),
                    weather_data.get('ruzgar_hizi', 15),
                    weather_data.get('yagis_7_gun', 10)
                )
                risk_seviyesi = self.get_risk_level(risk_skoru)
                
                # Cache'den analiz kontrolü
                cached_analysis = get_cached_analysis(
                    centroid_lat, centroid_lon, 
                    feature.get('properties', {}).get('area', 0),
                    feature.get('properties', {}).get('landuse', 'forest'),
                    feature.get('properties', {}).get('name', 'Orman Alanı')
                )
                
                if cached_analysis:
                    # Cache'den analiz verilerini al
                    feature['properties']['human_risk_score'] = cached_analysis.get('human_risk_score', 50)
                    feature['properties']['human_risk_factors'] = cached_analysis.get('human_risk_factors', [])
                    feature['properties']['lm_analysis'] = cached_analysis.get('analysis', 'LM analizi mevcut.')
                    feature['properties']['weather_weight'] = cached_analysis.get('weather_weight', 60.0)
                    feature['properties']['human_weight'] = cached_analysis.get('human_weight', 40.0)
                    feature['properties']['distance_from_city'] = cached_analysis.get('distance_from_city', 50.0)
                    feature['properties']['nearest_city'] = cached_analysis.get('nearest_city', 'bilinmiyor')
                else:
                    # Varsayılan değerler
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
            
            return feature
            
        except Exception as e:
            logging.error(f"Feature {i} işleme hatası: {str(e)}")
            return None

    def update_forest_risks(self):
        """
        Tüm orman alanlarının risk verilerini günceller (paralel işlem ile)
        """
        try:
            logging.info("Risk güncellemesi başlatılıyor...")
            
            # GeoJSON dosyasını yükle
            geojson_path = 'static/export_with_risk_latest.geojson'
            if not os.path.exists(geojson_path):
                logging.error(f"GeoJSON dosyası bulunamadı: {geojson_path}")
                return
                
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            
            logging.info(f"Toplam {len(geojson_data['features'])} alan işlenecek...")
            
            # Paralel işlem için ThreadPoolExecutor kullan
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Tüm feature'ları işlem için hazırla
                feature_data = [(i, feature) for i, feature in enumerate(geojson_data['features'])]
                
                # Paralel olarak işle
                future_to_feature = {executor.submit(self.process_single_feature, fd): fd for fd in feature_data}
                
                processed_count = 0
                for future in concurrent.futures.as_completed(future_to_feature):
                    result = future.result()
                    if result:
                        processed_count += 1
                        if processed_count % 50 == 0:
                            logging.info(f"İşlenen alan: {processed_count}/{len(geojson_data['features'])}")
            
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
            
            # LM analizi başladığını işaretle
            cache_manager.start_lm_analysis()
            
            geojson_path = 'static/export_with_risk_latest.geojson'
            fires_path = 'static/fires.json'
            fire_points = []
            
            if os.path.exists(fires_path):
                with open(fires_path, 'r', encoding='utf-8') as f:
                    fire_points = json.load(f)
                    
            if not os.path.exists(geojson_path):
                logging.error(f"GeoJSON dosyası bulunamadı: {geojson_path}")
                cache_manager.complete_lm_analysis()
                return
                
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
                
            logging.info(f"Toplam {len(geojson_data['features'])} alan LM analizi için hazırlanıyor...")
            
            # Paralel işlem için ThreadPoolExecutor kullan
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Tüm alanları analiz için hazırla
                feature_data = [(i, feature) for i, feature in enumerate(geojson_data['features'])]
                
                # Paralel olarak analiz et
                future_to_feature = {executor.submit(self.process_lm_single_feature, fd, fire_points): fd for fd in feature_data}
                
                processed_count = 0
                for future in concurrent.futures.as_completed(future_to_feature):
                    result = future.result()
                    if result:
                        processed_count += 1
                        if processed_count % 50 == 0:
                            logging.info(f"LM Analizi ilerleme: {processed_count}/{len(geojson_data['features'])} alan işlendi")
                    
            # Kaydet
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f'static/export_with_lm_risk_{timestamp}.geojson'
            
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(geojson_data, f, ensure_ascii=False, indent=2)
                    
                with open('static/export_with_lm_risk_latest.geojson', 'w', encoding='utf-8') as f:
                    json.dump(geojson_data, f, ensure_ascii=False, indent=2)
                    
                logging.info(f"Birleşik LM risk güncellemesi tamamlandı. Sonuç: {output_filename}")
                
            except Exception as e:
                logging.error(f"LM analizi dosya kaydetme hatası: {str(e)}")
                
            finally:
                # LM analizi tamamlandığını işaretle
                cache_manager.complete_lm_analysis()
                
        except Exception as e:
            logging.error(f"Birleşik LM risk güncellemesi sırasında hata: {str(e)}")
            cache_manager.complete_lm_analysis()

    def process_lm_single_feature(self, feature_data, fire_points):
        """
        Tek bir alanı LM analizi ile işler (paralel işlem için)
        """
        try:
            i, feature = feature_data
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
                    return None
                centroid_lat, centroid_lon = self.calculate_centroid(coordinates)
                
            if centroid_lat is None or centroid_lon is None:
                return None
                
            # Hava durumu verisini çek
            weather_data, error = self.get_weather_data_for_coordinates(centroid_lat, centroid_lon)
            if error or weather_data is None:
                logging.warning(f"Feature {i}: Hava durumu hatası - {error}")
                return None
                
            # LM analizli birleşik risk hesapla
            combined_risk = lm_analyzer.analyze_forest_area((centroid_lat, centroid_lon), weather_data, area_info)
            
            # Sonuçları properties'e yaz
            for k, v in combined_risk.items():
                feature['properties'][k] = v
                
            feature['properties']['son_guncelleme'] = datetime.now().isoformat()
            
            return feature
            
        except Exception as e:
            logging.error(f"Feature {i} LM analizi hatası: {str(e)}")
            return None

    def start_scheduler(self):
        """
        Zamanlayıcıyı başlatır
        """
        # Klasik risk güncellemesi - 12:00'de
        schedule.every().day.at("12:00").do(self.update_forest_risks)
        
        # LM destekli risk güncellemesi - 13:00'de (birleşik analiz bittikten sonra)
        schedule.every().day.at("13:00").do(self.update_forest_lm_risks)
        
        # Cache temizleme - 13:01'de (LM analizi bittikten sonra)
        schedule.every().day.at("13:01").do(cache_manager.clear_expired_cache)
        
        logging.info("Zamanlayıcı başlatıldı:")
        logging.info("- 12:00: Klasik risk güncellemesi")
        logging.info("- 13:00: LM destekli risk güncellemesi")
        logging.info("- 13:01: Cache temizleme")
        
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