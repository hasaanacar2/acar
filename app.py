from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from auto_updater import auto_updater
from lm_risk_analyzer import lm_analyzer, get_cached_analysis, cache_analysis, clear_expired_cache, cache_data, update_weather_date
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
    print("python-dotenv bulunamadı, environment variables manuel olarak ayarlanmalı")

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

# Groq API kontrolü
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
if not GROQ_API_KEY:
    print("⚠️ UYARI: GROQ_API_KEY bulunamadı! LM analizi dummy mod ile çalışacak.")
else:
    print("✅ GROQ_API_KEY bulundu. LM analizi aktif.")

# Not: forsts.geojson dosyasını 'static' klasörüne koymalısınız.

# Performans optimizasyonu için global değişkenler
weather_cache = {}  # Hava durumu cache'i
weather_cache_lock = threading.Lock()
MAX_WORKERS = 4  # Paralel işlem sayısı

# Rate limiting için
last_request_time = 0
request_lock = threading.Lock()
MIN_REQUEST_INTERVAL = 0.6  # Minimum 0.6 saniye aralık (dakikada 100 istek sınırı için)

def check_weather_rate_limit():
    """
    WeatherAPI.com rate limiting kontrolü
    """
    global last_request_time
    with request_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time
        if time_since_last < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - time_since_last
            time.sleep(sleep_time)
        last_request_time = time.time()

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
        # Rate limiting kontrolü
        check_weather_rate_limit()
        
        # 1 gün önceki 12:00'ı hesapla
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_noon = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)
        weather_date = yesterday_noon.strftime('%Y-%m-%d')
        
        # Yeni hava durumu tarihi kontrolü
        if update_weather_date(weather_date):
            print(f"🔄 Yeni hava durumu verisi tespit edildi: {weather_date}")
        
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
        # Rate limiting kontrolü
        check_weather_rate_limit()
        
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
    Geliştirilmiş orman yangını risk skoru hesaplama fonksiyonu
    Parametreler:
    - sicaklik: Celsius cinsinden sıcaklık
    - nem: Yüzde cinsinden nem oranı
    - ruzgar_hizi: km/h cinsinden rüzgar hızı
    - yagis_7_gun: mm cinsinden son 7 günlük yağış miktarı
    
    Döndürür: 0-100 arası risk skoru
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
        
        # Geliştirilmiş risk seviyesi belirleme
        if risk_skoru >= 75:
            risk_seviyesi = "Çok Yüksek"
            renk = "darkred"
        elif risk_skoru >= 60:
            risk_seviyesi = "Yüksek"
            renk = "red"
        elif risk_skoru >= 45:
            risk_seviyesi = "Orta-Yüksek"
            renk = "orange"
        elif risk_skoru >= 30:
            risk_seviyesi = "Orta"
            renk = "yellow"
        elif risk_skoru >= 20:
            risk_seviyesi = "Düşük-Orta"
            renk = "lightgreen"
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
    # Basit cache istatistikleri
    stats = {
        'total_entries': len(cache_data),
        'valid_entries': len(cache_data),
        'expired_entries': 0,
        'lm_analysis_running': False,
        'lm_analysis_completed': True
    }
    return jsonify(stats)

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """
    Süresi dolmuş cache'leri temizler
    """
    clear_expired_cache()
    return jsonify({'message': 'Cache temizlendi'})

@app.route('/analysis_status')
def analysis_status():
    """
    Başlangıç analizi durumunu döndürür
    """
    global initial_analysis_status
    stats = cache_manager.get_cache_stats()
    
    # Hava durumu güncelleme durumu
    from lm_risk_analyzer import last_weather_date
    weather_update_status = {
        'last_weather_date': last_weather_date,
        'cache_cleared': last_weather_date is not None
    }
    
    return jsonify({
        'cache_stats': stats,
        'server_started': True,
        'initial_analysis': initial_analysis_status,
        'lm_analysis_status': {
            'running': stats.get('lm_analysis_running', False),
            'completed': stats.get('lm_analysis_completed', False)
        },
        'weather_update': weather_update_status
    })

@app.route('/get_latest_geojson')
def get_latest_geojson():
    """En güncel GeoJSON dosya adını döndür"""
    try:
        # static klasöründeki GeoJSON dosyalarını kontrol et
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        geojson_files = [f for f in os.listdir(static_dir) if f.endswith('.geojson')]
        
        # En güncel dosyayı bul (export_with_risk_latest.geojson varsa onu kullan)
        if 'export_with_risk_latest.geojson' in geojson_files:
            filename = 'export_with_risk_latest.geojson'
        elif 'export_with_risk_auto' in str(geojson_files):
            # export_with_risk_auto ile başlayan en güncel dosyayı bul
            auto_files = [f for f in geojson_files if f.startswith('export_with_risk_auto')]
            if auto_files:
                filename = sorted(auto_files)[-1]  # En güncel dosya
            else:
                filename = 'export.geojson'  # Fallback
        else:
            filename = 'export.geojson'  # Fallback
        
        return jsonify({
            'filename': filename,
            'url': f'/static/{filename}'
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'filename': 'export.geojson',
            'url': '/static/export.geojson'
        }), 500

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
        cached_result = get_cached_analysis(
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
        cache_analysis(
            centroid_lat, centroid_lon, area, landuse, name, combined_risk
        )
        
        return jsonify(combined_risk)
    except Exception as e:
        return jsonify({'hata': str(e)}), 400

@app.route('/analyze_all_areas', methods=['POST'])
def analyze_all_areas():
    """
    Tüm alanları analiz eder ve sonuçları döndürür
    """
    try:
        # GeoJSON dosyasını oku
        geojson_path = 'static/export_with_risk_latest.geojson'
        if not os.path.exists(geojson_path):
            return jsonify({'error': 'GeoJSON dosyası bulunamadı'}), 404
            
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        results = []
        total_areas = len(geojson_data['features'])
        
        print(f"Tüm alanlar analiz ediliyor: {total_areas} alan")
        
        for i, feature in enumerate(geojson_data['features']):
            try:
                properties = feature.get('properties', {})
                centroid_lat = properties.get('centroid_lat')
                centroid_lon = properties.get('centroid_lon')
                area = properties.get('area', 0)
                landuse = properties.get('landuse', 'forest')
                name = properties.get('name', 'Orman Alanı')
                
                if centroid_lat is None or centroid_lon is None:
                    continue
                
                # Cache kontrolü
                cached_result = get_cached_analysis(
                    centroid_lat, centroid_lon, area, landuse, name
                )
                
                if cached_result:
                    results.append({
                        'index': i,
                        'name': name,
                        'data': cached_result,
                        'cached': True
                    })
                    print(f"Cache hit: {i+1}/{total_areas} - {name}")
                else:
                    # Yeni analiz
                    area_info = {
                        'landuse': landuse,
                        'area': area,
                        'name': name
                    }
                    
                    # Hava durumu verisini çek
                    weather_data, error = get_weather_data_for_coordinates(centroid_lat, centroid_lon)
                    if error or weather_data is None:
                        print(f"Hava durumu hatası: {name} - {error}")
                        continue
                    
                    # LM analizini çalıştır
                    combined_risk = lm_analyzer.analyze_forest_area(
                        (centroid_lat, centroid_lon),
                        weather_data,
                        area_info
                    )
                    
                    # Sonucu cache'e kaydet
                    cache_analysis(
                        centroid_lat, centroid_lon, area, landuse, name, combined_risk
                    )
                    
                    results.append({
                        'index': i,
                        'name': name,
                        'data': combined_risk,
                        'cached': False
                    })
                    
                    print(f"Analiz edildi: {i+1}/{total_areas} - {name}")
                
            except Exception as e:
                print(f"Alan analiz hatası ({name}): {str(e)}")
                continue
        
        print(f"Tüm analizler tamamlandı: {len(results)} alan")
        return jsonify({
            'success': True,
            'total_areas': total_areas,
            'analyzed_areas': len(results),
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_cached_analyses')
def get_cached_analyses():
    """
    Sadece cache'deki analizleri döndürür
    """
    try:
        # GeoJSON dosyasını oku
        geojson_path = 'static/export_with_risk_latest.geojson'
        if not os.path.exists(geojson_path):
            return jsonify({'error': 'GeoJSON dosyası bulunamadı'}), 404
            
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        cached_results = []
        
        for i, feature in enumerate(geojson_data['features']):
            try:
                properties = feature.get('properties', {})
                centroid_lat = properties.get('centroid_lat')
                centroid_lon = properties.get('centroid_lon')
                area = properties.get('area', 0)
                landuse = properties.get('landuse', 'forest')
                name = properties.get('name', 'Orman Alanı')
                
                if centroid_lat is None or centroid_lon is None:
                    continue
                
                # Sadece cache'den kontrol et
                cached_result = get_cached_analysis(
                    centroid_lat, centroid_lon, area, landuse, name
                )
                
                if cached_result:
                    cached_results.append({
                        'index': i,
                        'name': name,
                        'data': cached_result,
                        'cached': True
                    })
                    print(f"Cache'den alındı: {name}")
                
            except Exception as e:
                print(f"Cache kontrol hatası ({name}): {str(e)}")
                continue
        
        print(f"Cache'den {len(cached_results)} alan bulundu")
        return jsonify({
            'success': True,
            'total_areas': len(geojson_data['features']),
            'cached_areas': len(cached_results),
            'results': cached_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def initial_analysis():
    print("DEBUG: Başlangıç analizi fonksiyonu çağrıldı")
    global initial_analysis_status
    try:
        geojson_path = 'static/export_with_risk_latest.geojson'
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
    
    # Günlük cache temizleme scheduler'ı
    def daily_cache_cleanup():
        while True:
            try:
                time.sleep(3600)  # Her saat kontrol et
                now = datetime.now()
                if now.hour == 0:  # Gece yarısı
                    print("🕛 Günlük cache temizleme başlatılıyor...")
                    clear_expired_cache()
                    print("✅ Cache temizleme tamamlandı")
            except Exception as e:
                print(f"Cache temizleme hatası: {e}")
    
    cleanup_thread = threading.Thread(target=daily_cache_cleanup, daemon=True)
    cleanup_thread.start()
    print("✓ Günlük cache temizleme başlatıldı")
    
    # Başlangıç analizini garanti et
    print("✓ Başlangıç analizi başlatılıyor...")
    analysis_thread = threading.Thread(target=initial_analysis, daemon=True)
    analysis_thread.start()
    
    # Analiz başladığını doğrula
    time.sleep(0.5)  # 0.5 saniye bekle (azaltıldı)
    print("✓ Analiz thread başlatıldı")
    
    try:
        # Render için port ayarı
        port = int(os.environ.get('PORT', 5000))
        print(f"✓ Web sunucusu başlatılıyor: http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n⚠️ Uygulama kapatılıyor...")
        auto_updater.stop() 