import json
import requests
import time
from datetime import datetime, timedelta

# WeatherAPI.com API anahtarı
WEATHERAPI_KEY = "ca1b321f6c3948438c8181905250607"

def get_weather_data_for_coordinates(lat, lon):
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
        data = response.json()
        
        if response.status_code != 200:
            return None, f"WeatherAPI Hatası: {data.get('error', {}).get('message', 'Bilinmeyen hata')}"
        
        current = data['current']
        
        # WeatherAPI.com verilerini topla
        weather_info = {
            'sicaklik': current['temp_c'],
            'nem': current['humidity'],
            'ruzgar_hizi': current['wind_kph'],  # Zaten km/h cinsinden
            'yagis_7_gun': 0  # Basitlik için 0 olarak ayarla
        }
        
        return weather_info, None
        
    except Exception as e:
        return None, f"Veri çekme hatası: {str(e)}"

def hesapla_risk_skoru(sicaklik, nem, ruzgar_hizi, yagis_7_gun):
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

def get_risk_level(risk_skoru):
    """
    Risk skoruna göre seviye belirleme
    """
    if risk_skoru >= 70:
        return "Yüksek"
    elif risk_skoru >= 40:
        return "Orta"
    else:
        return "Düşük"

def calculate_centroid(coordinates):
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

def process_geojson():
    """
    Geliştirilmiş GeoJSON dosyasını işleyip her küçük alan için risk hesaplama
    """
    print("Geliştirilmiş GeoJSON dosyası okunuyor...")
    
    # Geliştirilmiş GeoJSON dosyasını oku
    with open('static/export_improved.geojson', 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    print(f"Toplam {len(geojson_data['features'])} küçük alan bulundu.")
    
    # Her feature için risk hesapla
    for i, feature in enumerate(geojson_data['features']):
        print(f"İşleniyor: {i+1}/{len(geojson_data['features'])}")
        
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
                print(f"Desteklenmeyen geometry tipi: {geometry['type']}")
                continue
            centroid_lat, centroid_lon = calculate_centroid(coordinates)
        
        if centroid_lat is None or centroid_lon is None:
            print(f"Centroid hesaplanamadı: Feature {i}")
            continue
        
        # Hava durumu verilerini çek
        weather_data, error = get_weather_data_for_coordinates(centroid_lat, centroid_lon)
        
        if error or weather_data is None:
            print(f"Hava durumu verisi çekilemedi: {error}")
            # Varsayılan risk değerleri
            risk_skoru = 50
            risk_seviyesi = "Orta"
        else:
            # Risk hesapla
            risk_skoru = hesapla_risk_skoru(
                weather_data['sicaklik'],
                weather_data['nem'],
                weather_data['ruzgar_hizi'],
                weather_data['yagis_7_gun']
            )
            risk_seviyesi = get_risk_level(risk_skoru)
        
        # Properties'e risk bilgilerini ekle
        if 'properties' not in feature:
            feature['properties'] = {}
        
        feature['properties']['risk_skoru'] = risk_skoru
        feature['properties']['risk_seviyesi'] = risk_seviyesi
        if weather_data is not None:
            feature['properties']['sicaklik'] = weather_data.get('sicaklik', 0)
            feature['properties']['nem'] = weather_data.get('nem', 0)
            feature['properties']['ruzgar_hizi'] = weather_data.get('ruzgar_hizi', 0)
            feature['properties']['yagis_7_gun'] = weather_data.get('yagis_7_gun', 0)
    
    # Sonucu yeni dosyaya kaydet
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"static/export_with_risk_auto_{timestamp}.geojson"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Riskli GeoJSON kaydedildi: {out_path}")
    print(f"Toplam {len(geojson_data['features'])} alan işlendi.")
    return out_path

if __name__ == "__main__":
    process_geojson() 