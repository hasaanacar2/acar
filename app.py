from flask import Flask, render_template, request, jsonify, make_response, send_file
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
import hashlib
from functools import lru_cache

# Environment variables yükle
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv bulunamadı, environment variables manuel olarak ayarlanmalı")

app = Flask(__name__)

# Global değişkenler
ANALYZED_GEOJSON_PATH = 'static/analyzed_data.json'
ANALYSIS_LOCK = threading.Lock()
LAST_ANALYSIS_TIME = None
ANALYSIS_IN_PROGRESS = False

# WeatherAPI.com API anahtarı
WEATHERAPI_KEY = os.environ.get('WEATHERAPI_KEY', "ca1b321f6c3948438c8181905250607")

# Groq API kontrolü
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
if not GROQ_API_KEY:
    print("⚠️ UYARI: GROQ_API_KEY bulunamadı! LM analizi dummy mod ile çalışacak.")
else:
    print("✅ GROQ_API_KEY bulundu. LM analizi aktif.")

# Performans optimizasyonu için global değişkenler
weather_cache = {}
weather_cache_lock = threading.Lock()
MAX_WORKERS = 2  # API limiti için azaltıldı
API_DELAY = 0.7  # 100 req/min için güvenli gecikme

# Rate limiting
last_request_time = 0
request_lock = threading.Lock()
request_queue = []

def check_api_rate_limit():
    """API rate limiting kontrolü - dakikada maksimum 100 istek"""
    global last_request_time
    with request_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time
        
        # Minimum 0.6 saniye bekle (100 req/min = 1.67 req/sec)
        if time_since_last < API_DELAY:
            sleep_time = API_DELAY - time_since_last
            time.sleep(sleep_time)
        
        last_request_time = time.time()

def get_weather_data_for_coordinates(lat, lon, use_cache=True):
    """Belirli koordinatlar için hava durumu verilerini çeker"""
    cache_key = f"{lat:.4f}_{lon:.4f}"
    
    # Cache kontrolü
    if use_cache:
        with weather_cache_lock:
            if cache_key in weather_cache:
                cache_time, weather_data = weather_cache[cache_key]
                # 23 saat cache (günlük güncelleme için)
                if time.time() - cache_time < 82800:  # 23 saat
                    return weather_data, None
    
    try:
        # Rate limit kontrolü
        check_api_rate_limit()
        
        # Bugünün 12:00 verisi
        today = datetime.now()
        today_noon = today.replace(hour=12, minute=0, second=0, microsecond=0)
        
        # Eğer henüz 12:00 olmadıysa dünün verisini al
        if today.hour < 12:
            today_noon = today_noon - timedelta(days=1)
        
        weather_date = today_noon.strftime('%Y-%m-%d')
        
        # Saat 12:00'dan sonraysa güncel veri, öncesiyse history API
        if today.hour >= 12 and today_noon.date() == today.date():
            # Güncel veri için current API kullan
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': WEATHERAPI_KEY,
                'q': f"{lat},{lon}",
                'aqi': 'no'
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                error_data = response.json()
                print(f"WeatherAPI Hatası ({response.status_code}): {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}")
                return None, "API Hatası"
            
            data = response.json()
            current = data['current']
            
            weather_info = {
                'sicaklik': current['temp_c'],
                'nem': current['humidity'],
                'ruzgar_hizi': current['wind_kph'],
                'yagis_7_gun': current.get('precip_mm', 0),
                'data_time': today_noon.isoformat()
            }
        else:
            # Geçmiş veri için history API kullan
            url = "http://api.weatherapi.com/v1/history.json"
            params = {
                'key': WEATHERAPI_KEY,
                'q': f"{lat},{lon}",
                'dt': weather_date,
                'aqi': 'no'
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                error_data = response.json()
                print(f"WeatherAPI Hatası ({response.status_code}): {error_data.get('error', {}).get('message', 'Bilinmeyen hata')}")
                return None, "API Hatası"
            
            data = response.json()
            
            if 'forecast' in data and 'forecastday' in data['forecast'] and len(data['forecast']['forecastday']) > 0:
                forecast_day = data['forecast']['forecastday'][0]
                hour_data = forecast_day['hour'][12]  # 12:00 verisi
                
                weather_info = {
                    'sicaklik': hour_data['temp_c'],
                    'nem': hour_data['humidity'],
                    'ruzgar_hizi': hour_data['wind_kph'],
                    'yagis_7_gun': hour_data.get('precip_mm', 0),
                    'data_time': today_noon.isoformat()
                }
            else:
                return None, "12:00 verisi bulunamadı"
        
        # Cache'e kaydet
        with weather_cache_lock:
            weather_cache[cache_key] = (time.time(), weather_info)
        
        print(f"Hava durumu alındı: {weather_date} 12:00 - {lat:.4f}, {lon:.4f}")
        return weather_info, None
        
    except Exception as e:
        print(f"Veri çekme hatası: {str(e)}")
        return None, str(e)

def analyze_single_area(feature_data):
    """Tek bir alanı analiz eder"""
    try:
        feature = feature_data
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
            # Cache'den gelen veriyi direkt properties'e ekle
            for key, value in cached_result.items():
                properties[key] = value
            return feature
        
        # Hava durumu verisi
        weather_data, error = get_weather_data_for_coordinates(centroid_lat, centroid_lon)
        if error or weather_data is None:
            print(f"Hava durumu hatası {name}: {error}")
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
        
        # Sonuçları properties'e ekle
        for key, value in combined_risk.items():
            properties[key] = value
        
        properties['analyzed_at'] = datetime.now().isoformat()
        
        return feature
        
    except Exception as e:
        print(f"Analiz hatası: {str(e)}")
        return None

def analyze_all_areas_backend(force_refresh=False):
    """Tüm alanları backend'de analiz eder ve sonucu kaydeder"""
    global ANALYSIS_IN_PROGRESS, LAST_ANALYSIS_TIME
    
    with ANALYSIS_LOCK:
        if ANALYSIS_IN_PROGRESS:
            print("Analiz zaten devam ediyor...")
            return False
        ANALYSIS_IN_PROGRESS = True
    
    try:
        print("=== BACKEND ANALİZİ BAŞLATILIYOR ===")
        print(f"Tarih/Saat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Force Refresh: {force_refresh}")
        start_time = time.time()
        
        # Force refresh ise cache'i temizle
        if force_refresh:
            print("Cache temizleniyor...")
            with weather_cache_lock:
                weather_cache.clear()
            cache_manager.clear_expired_cache()
        
        # GeoJSON dosyasını yükle
        geojson_path = 'static/export_with_risk_latest.geojson'
        if not os.path.exists(geojson_path):
            print(f"GeoJSON dosyası bulunamadı: {geojson_path}")
            return False
            
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        total_features = len(geojson_data['features'])
        print(f"Toplam {total_features} alan analiz edilecek...")
        print(f"Hedef: Bugünün 12:00 verisi")
        
        analyzed_features = []
        cached_count = 0
        new_count = 0
        failed_count = 0
        
        # Sıralı analiz (API limiti için)
        for i, feature in enumerate(geojson_data['features']):
            if i % 10 == 0:
                print(f"İlerleme: {i}/{total_features} (Cache: {cached_count}, Yeni: {new_count}, Hata: {failed_count})")
            
            # Force refresh değilse ve önceki analiz varsa kontrol et
            if not force_refresh and all(key in feature.get('properties', {}) for key in ['combined_risk_score', 'combined_risk_level', 'weather_data']):
                # Son 23 saat içinde analiz edilmişse atla
                analyzed_at = feature['properties'].get('analyzed_at')
                if analyzed_at:
                    analysis_time = datetime.fromisoformat(analyzed_at)
                    if (datetime.now() - analysis_time).total_seconds() < 82800:  # 23 saat
                        cached_count += 1
                        analyzed_features.append(feature)
                        continue
            
            # Yeni analiz
            result = analyze_single_area(feature)
            if result:
                analyzed_features.append(result)
                new_count += 1
            else:
                failed_count += 1
                # Hatalı alanı da ekle ama analiz edilmemiş olarak işaretle
                feature['properties']['analysis_failed'] = True
                analyzed_features.append(feature)
            
            # API rate limit için bekleme
            if new_count > 0 and new_count % 5 == 0:
                time.sleep(1)  # Her 5 yeni analizde 1 saniye bekle
        
        # Analiz edilmiş veriyi kaydet
        analyzed_data = {
            'type': 'FeatureCollection',
            'features': analyzed_features,
            'metadata': {
                'total_areas': total_features,
                'analyzed_areas': len(analyzed_features) - failed_count,
                'cached_areas': cached_count,
                'new_analyses': new_count,
                'failed_analyses': failed_count,
                'analysis_date': datetime.now().isoformat(),
                'weather_date': datetime.now().replace(hour=12, minute=0, second=0).isoformat(),
                'analysis_duration': time.time() - start_time
            }
        }
        
        # Dosyaya kaydet
        with open(ANALYZED_GEOJSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(analyzed_data, f, ensure_ascii=False, indent=2)
        
        LAST_ANALYSIS_TIME = datetime.now()
        
        print(f"""
=== ANALİZ TAMAMLANDI ===
Toplam: {total_features} alan
Cache'den: {cached_count} alan
Yeni analiz: {new_count} alan
Başarısız: {failed_count} alan
Süre: {time.time() - start_time:.2f} saniye
Veri zamanı: Bugün 12:00
========================
        """)
        
        return True
        
    except Exception as e:
        print(f"Backend analiz hatası: {str(e)}")
        return False
    finally:
        ANALYSIS_IN_PROGRESS = False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_analyzed_data')
def get_analyzed_data():
    """Analiz edilmiş veriyi döndürür"""
    try:
        # Analiz edilmiş dosya var mı kontrol et
        if not os.path.exists(ANALYZED_GEOJSON_PATH):
            # Yoksa analizi başlat
            analyze_thread = threading.Thread(target=analyze_all_areas_backend)
            analyze_thread.start()
            
            return jsonify({
                'status': 'analyzing',
                'message': 'Analiz başlatıldı, lütfen bekleyin...'
            }), 202
        
        # Dosya yaşını kontrol et
        file_age = time.time() - os.path.getmtime(ANALYZED_GEOJSON_PATH)
        if file_age > 3600:  # 1 saatten eski
            # Arka planda yeni analiz başlat
            if not ANALYSIS_IN_PROGRESS:
                analyze_thread = threading.Thread(target=analyze_all_areas_backend)
                analyze_thread.start()
        
        # Mevcut dosyayı gönder
        return send_file(ANALYZED_GEOJSON_PATH, mimetype='application/json')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analysis_status')
def analysis_status():
    """Analiz durumunu döndürür"""
    try:
        metadata = None
        if os.path.exists(ANALYZED_GEOJSON_PATH):
            with open(ANALYZED_GEOJSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metadata = data.get('metadata', {})
        
        return jsonify({
            'analyzing': ANALYSIS_IN_PROGRESS,
            'last_analysis': LAST_ANALYSIS_TIME.isoformat() if LAST_ANALYSIS_TIME else None,
            'metadata': metadata,
            'cache_stats': cache_manager.get_cache_stats()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/trigger_analysis', methods=['POST'])
def trigger_analysis():
    """Manuel olarak analiz başlatır"""
    if ANALYSIS_IN_PROGRESS:
        return jsonify({
            'status': 'already_running',
            'message': 'Analiz zaten devam ediyor'
        }), 409
    
    analyze_thread = threading.Thread(target=analyze_all_areas_backend)
    analyze_thread.start()
    
    return jsonify({
        'status': 'started',
        'message': 'Analiz başlatıldı'
    })

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """Cache'i temizler"""
    clear_expired_cache()
    with weather_cache_lock:
        weather_cache.clear()
    return jsonify({'message': 'Cache temizlendi'})

# Static dosyalar için cache headers
@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        if request.path.endswith('.json'):
            response.headers['Cache-Control'] = 'no-cache, must-revalidate'
        else:
            response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

def startup_analysis():
    """Sunucu başladığında analizi kontrol et"""
    time.sleep(2)  # Flask'ın başlamasını bekle
    
    if not os.path.exists(ANALYZED_GEOJSON_PATH):
        print("Analiz dosyası bulunamadı, yeni analiz başlatılıyor...")
        analyze_all_areas_backend()
    else:
        file_age = time.time() - os.path.getmtime(ANALYZED_GEOJSON_PATH)
        if file_age > 3600:
            print(f"Analiz dosyası {file_age/3600:.1f} saat eski, yenileniyor...")
            analyze_all_areas_backend()
        else:
            print(f"Güncel analiz mevcut ({file_age/60:.1f} dakika önce)")

if __name__ == '__main__':
    print("=== ORMAN ERKEN UYARI SİSTEMİ BAŞLATILIYOR ===")
    
    # Auto updater'ı başlat
    auto_updater.start()
    print("✓ Auto updater başlatıldı")
    
    # Başlangıç analizini başlat
    def startup_analysis():
        time.sleep(2)  # Flask'ın başlamasını bekle
        
        if not os.path.exists(ANALYZED_GEOJSON_PATH):
            print("Analiz dosyası bulunamadı, yeni analiz başlatılıyor...")
            analyze_all_areas_backend()
        else:
            # Dosyanın metadata'sını kontrol et
            try:
                with open(ANALYZED_GEOJSON_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata = data.get('metadata', {})
                    
                if metadata.get('analysis_date'):
                    analysis_date = datetime.fromisoformat(metadata['analysis_date'])
                    hours_old = (datetime.now() - analysis_date).total_seconds() / 3600
                    
                    if hours_old > 24:
                        print(f"Analiz {hours_old:.1f} saat eski, yenileniyor...")
                        analyze_all_areas_backend(force_refresh=True)
                    else:
                        print(f"Güncel analiz mevcut ({hours_old:.1f} saat önce)")
                else:
                    print("Metadata bulunamadı, yeni analiz başlatılıyor...")
                    analyze_all_areas_backend()
            except Exception as e:
                print(f"Dosya okuma hatası: {e}, yeni analiz başlatılıyor...")
                analyze_all_areas_backend()
    
    startup_thread = threading.Thread(target=startup_analysis, daemon=True)
    startup_thread.start()
    print("✓ Başlangıç analizi kontrol ediliyor...")
    
    # Günlük otomatik analiz - Her gün 12:15'te (12:00 verileri hazır olduğunda)
    def daily_analysis():
        while True:
            try:
                now = datetime.now()
                # Bir sonraki 12:15'i hesapla
                next_run = now.replace(hour=12, minute=15, second=0, microsecond=0)
                if now >= next_run:
                    next_run += timedelta(days=1)
                
                # Bekleme süresi
                wait_seconds = (next_run - now).total_seconds()
                print(f"Sonraki otomatik analiz: {next_run.strftime('%Y-%m-%d %H:%M:%S')} ({wait_seconds/3600:.1f} saat sonra)")
                
                time.sleep(wait_seconds)
                
                print("📊 Günlük analiz başlatılıyor (12:00 verileri)...")
                analyze_all_areas_backend(force_refresh=True)
                
            except Exception as e:
                print(f"Günlük analiz hatası: {e}")
                time.sleep(3600)  # Hata durumunda 1 saat bekle
    
    daily_thread = threading.Thread(target=daily_analysis, daemon=True)
    daily_thread.start()
    print("✓ Günlük analiz scheduler'ı başlatıldı (Her gün 12:15)")
    
    try:
        # Render için port ayarı
        port = int(os.environ.get('PORT', 5000))
        print(f"✓ Web sunucusu başlatılıyor: http://localhost:{port}")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n⚠️ Uygulama kapatılıyor...")
        auto_updater.stop()
