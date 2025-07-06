from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from auto_updater import auto_updater
from lm_risk_analyzer import lm_analyzer
from cache_manager import cache_manager
import threading
import concurrent.futures
import time
import json

# Environment variables yükle
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

# Global analiz durumu
initial_analysis_status = {
    'running': False,
    'completed': False,
    'total_areas': 0,
    'analyzed_count': 0,
    'cached_count': 0
}

# WeatherAPI.com API anahtarı - environment variable'dan al
WEATHERAPI_KEY = os.environ.get('WEATHERAPI_KEY', "ca1b321f6c3948438c8181905250607")
# Buraya API anahtarınızı ekleyin

# Not: forsts.geojson dosyasını 'static' klasörüne koymalısınız.

# Performans optimizasyonu için global değişkenler
weather_cache = {}  # Hava durumu cache'i
weather_cache_lock = threading.Lock()
MAX_WORKERS = 4  # Paralel işlem sayısı

def get_weather_data_for_coordinates(lat, lon):
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
        # 1 gün önceki 12:00'ı hesapla
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_noon = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)
        
        # WeatherAPI.com çağrısı - Geçmiş veri için
        url = "http://api.weatherapi.com/v1/history.json"
        params = {
            'key': WEATHERAPI_KEY,
            'q': f"{lat},{lon}",
            'dt': yesterday_noon.strftime('%Y-%m-%d'),
            'aqi': 'no'
        }
        
        response = requests.get(url, params=params, timeout=5)  # Timeout azaltıldı
        
        if response.status_code != 200:
            error_data = response.json()
            print(f"WeatherAPI Hatası ({response.status_code}): {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}")
            # Hata durumunda mevcut veriyi kullan
            return get_current_weather_data(lat, lon)
        
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
            
            print(f"1 gün önceki 12:00 verisi kullanıldı: {lat}, {lon}")
            return weather_info, None
        else:
            # Geçmiş veri yoksa mevcut veriyi al
            return get_current_weather_data(lat, lon)
            
    except requests.exceptions.Timeout:
        print(f"API timeout: {lat}, {lon}")
        return get_current_weather_data(lat, lon)
    except requests.exceptions.RequestException as e:
        print(f"API bağlantı hatası: {str(e)}")
        return get_current_weather_data(lat, lon)
    except Exception as e:
        print(f"Veri çekme hatası: {str(e)}")
        return get_current_weather_data(lat, lon)

def get_current_weather_data(lat, lon):
    """
    Mevcut hava durumu verilerini çeker (fallback için)
    """
    try:
        url = "http://api.weatherapi.com/v1/current.json"
        params = {
            'key': WEATHERAPI_KEY,
            'q': f"{lat},{lon}",
            'aqi': 'no'
        }
        
        response = requests.get(url, params=params, timeout=5)  # Timeout azaltıldı
        data = response.json()
        
        if response.status_code != 200:
            return None, f"WeatherAPI Hatası: {data.get('error', {}).get('message', 'Bilinmeyen hata')}"
        
        current = data['current']
        
        weather_info = {
            'sicaklik': current['temp_c'],
            'nem': current['humidity'],
            'ruzgar_hizi': current['wind_kph'],
            'yagis_7_gun': 0
        }
        
        return weather_info, None
        
    except Exception as e:
        return None, f"Veri çekme hatası: {str(e)}"

def analyze_single_area(feature_data):
    """
    Tek bir alanı analiz eder (paralel işlem için)
    """
    try:
        i, feature = feature_data
        properties = feature.get('properties', {})
        centroid_lat = properties.get('centroid_lat')
        centroid_lon = properties.get('centroid_lon')
        area = properties.get('area', 0)
        landuse = properties.get('landuse', 'forest')
        name = properties.get('name', 'Orman Alanı')
        
        if centroid_lat is None or centroid_lon is None:
            return None
        
        # Cache kontrolü
        cached_result = cache_manager.get_cached_analysis(
            centroid_lat, centroid_lon, area, landuse, name
        )
        
        if cached_result:
            return {'type': 'cached', 'index': i, 'name': name}
        
        # Hava durumu verisi
        weather_data, error = get_weather_data_for_coordinates(centroid_lat, centroid_lon)
        if error or weather_data is None:
            return None
        
        # LM analizi
        area_info = {
            'landuse': landuse,
            'area': area,
            'name': name
        }
        
        combined_risk = lm_analyzer.analyze_forest_area(
            (centroid_lat, centroid_lon),
            weather_data,
            area_info
        )
        
        # Cache'e kaydet
        cache_manager.cache_analysis(
            centroid_lat, centroid_lon, area, landuse, name, combined_risk
        )
        
        return {'type': 'analyzed', 'index': i, 'name': name}
        
    except Exception as e:
        print(f"Analiz hatası (alan {i}): {str(e)}")
        return None

def hesapla_risk_skoru(sicaklik, nem, ruzgar_hizi, yagis_7_gun):
    """
    Orman yangını risk skoru hesaplama fonksiyonu
    Parametreler:
    - sicaklik: Celsius cinsinden sıcaklık
    - nem: Yüzde cinsinden nem oranı
    - ruzgar_hizi: km/h cinsinden rüzgar hızı
    - yagis_7_gun: mm cinsinden son 7 günlük yağış miktarı
    
    Döndürür: 0-100 arası risk skoru
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
    
    return min(risk_skoru, 100)  # Maksimum 100

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_weather', methods=['POST'])
def get_weather():
    try:
        data = request.get_json()
        lat = data.get('lat', 41.0082)  # İstanbul varsayılan
        lon = data.get('lon', 28.9784)  # İstanbul varsayılan
        
        weather_data, error = get_weather_data_for_coordinates(lat, lon)
        
        if error:
            return jsonify({'hata': error}), 400
        
        return jsonify(weather_data)
        
    except Exception as e:
        return jsonify({'hata': str(e)}), 400

@app.route('/hesapla_risk', methods=['POST'])
def hesapla_risk():
    try:
        data = request.get_json()
        sicaklik = float(data['sicaklik'])
        nem = float(data['nem'])
        ruzgar_hizi = float(data['ruzgar_hizi'])
        yagis_7_gun = float(data['yagis_7_gun'])
        
        risk_skoru = hesapla_risk_skoru(sicaklik, nem, ruzgar_hizi, yagis_7_gun)
        
        # Risk seviyesi belirleme
        if risk_skoru >= 70:
            risk_seviyesi = "Yüksek"
            renk = "red"
        elif risk_skoru >= 40:
            risk_seviyesi = "Orta"
            renk = "orange"
        else:
            risk_seviyesi = "Düşük"
            renk = "green"
        
        return jsonify({
            'risk_skoru': risk_skoru,
            'risk_seviyesi': risk_seviyesi,
            'renk': renk
        })
    except Exception as e:
        return jsonify({'hata': str(e)}), 400

@app.route('/status')
def status():
    """
    Auto updater durumunu kontrol eder
    """
    return jsonify({
        'auto_updater_running': auto_updater.is_running,
        'last_update': auto_updater.last_update if hasattr(auto_updater, 'last_update') else None
    })

@app.route('/cache_stats')
def cache_stats():
    """
    Cache istatistiklerini döndürür
    """
    stats = cache_manager.get_cache_stats()
    return jsonify(stats)

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """
    Süresi dolmuş cache'leri temizler
    """
    cache_manager.clear_expired_cache()
    return jsonify({'message': 'Cache temizlendi'})

@app.route('/analysis_status')
def analysis_status():
    """
    Başlangıç analizi durumunu döndürür
    """
    global initial_analysis_status
    stats = cache_manager.get_cache_stats()
    
    return jsonify({
        'cache_stats': stats,
        'server_started': True,
        'initial_analysis': initial_analysis_status,
        'lm_analysis_status': {
            'running': stats.get('lm_analysis_running', False),
            'completed': stats.get('lm_analysis_completed', False)
        }
    })

@app.route('/analyze_lm', methods=['POST'])
def analyze_lm():
    try:
        data = request.get_json()
        centroid_lat = float(data['centroid_lat'])
        centroid_lon = float(data['centroid_lon'])
        area = float(data.get('area', 0))
        landuse = data.get('landuse', 'forest')
        name = data.get('name', 'Orman Alanı')

        # Önce cache'den kontrol et
        cached_result = cache_manager.get_cached_analysis(
            centroid_lat, centroid_lon, area, landuse, name
        )
        
        if cached_result:
            response = jsonify(cached_result)
            response.headers['X-Cache-Hit'] = 'true'
            return response

        area_info = {
            'landuse': landuse,
            'area': area,
            'name': name
        }

        # Hava durumu verisini çek
        weather_data, error = get_weather_data_for_coordinates(centroid_lat, centroid_lon)
        if error or weather_data is None:
            return jsonify({'hata': error or 'Hava durumu verisi alınamadı'}), 400

        # LM analizini çalıştır
        combined_risk = lm_analyzer.analyze_forest_area(
            (centroid_lat, centroid_lon),
            weather_data,
            area_info
        )
        
        # Sonucu cache'e kaydet
        cache_manager.cache_analysis(
            centroid_lat, centroid_lon, area, landuse, name, combined_risk
        )
        
        return jsonify(combined_risk)
    except Exception as e:
        return jsonify({'hata': str(e)}), 400

def initial_analysis():
    print("DEBUG: Başlangıç analizi fonksiyonu çağrıldı")
    global initial_analysis_status
    try:
        geojson_path = 'static/export_improved.geojson'
        if not os.path.exists(geojson_path):
            print(f"GeoJSON dosyası bulunamadı: {geojson_path}")
            return
            
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
            
        initial_analysis_status['running'] = True
        initial_analysis_status['total_areas'] = len(geojson_data['features'])
        initial_analysis_status['analyzed_count'] = 0
        initial_analysis_status['cached_count'] = 0
        
        print(f"Başlangıç analizi başlatılıyor... {len(geojson_data['features'])} alan analiz edilecek")
        
        analyzed_count = 0
        cached_count = 0
        
        # Paralel analiz için ThreadPoolExecutor kullan
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Tüm alanları analiz için hazırla
            feature_data = [(i, feature) for i, feature in enumerate(geojson_data['features'])]
            
            # Paralel olarak analiz et
            future_to_feature = {executor.submit(analyze_single_area, fd): fd for fd in feature_data}
            
            for future in concurrent.futures.as_completed(future_to_feature):
                result = future.result()
                if result:
                    if result['type'] == 'cached':
                        cached_count += 1
                        initial_analysis_status['cached_count'] = cached_count
                        if result['index'] % 20 == 0:
                            print(f"Cache hit: {result['index']+1}/{len(geojson_data['features'])} - {result['name']}")
                    else:
                        analyzed_count += 1
                        initial_analysis_status['analyzed_count'] = analyzed_count
                        if result['index'] % 20 == 0:
                            print(f"Analiz edildi: {result['index']+1}/{len(geojson_data['features'])} - {result['name']}")
        
        initial_analysis_status['running'] = False
        initial_analysis_status['completed'] = True
        print(f"Başlangıç analizi tamamlandı! {analyzed_count} yeni analiz, {cached_count} cache hit")
        
    except Exception as e:
        initial_analysis_status['running'] = False
        print(f"Başlangıç analizi hatası: {str(e)}")
    print("DEBUG: Başlangıç analizi fonksiyonu bitti")

if __name__ == '__main__':
    print("=== ORMAN ERKEN UYARI SİSTEMİ BAŞLATILIYOR ===")
    
    # Auto updater'ı başlat
    auto_updater.start()
    print("✓ Auto updater başlatıldı")
    
    # Başlangıç analizini garanti et
    print("✓ Başlangıç analizi başlatılıyor...")
    analysis_thread = threading.Thread(target=initial_analysis, daemon=True)
    analysis_thread.start()
    
    # Analiz başladığını doğrula
    time.sleep(0.5)  # 0.5 saniye bekle (azaltıldı)
    print("✓ Analiz thread başlatıldı")
    
    try:
        port = int(os.environ.get('PORT', 5000))
        print(f"✓ Web sunucusu başlatılıyor: http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("\n⚠️ Uygulama kapatılıyor...")
        auto_updater.stop() 