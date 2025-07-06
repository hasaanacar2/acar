import json
import time
from datetime import datetime
import random

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

def generate_test_weather_data():
    """
    Test için gerçekçi hava durumu verileri üretir
    """
    # Yaz aylarında daha yüksek sıcaklık ve düşük nem
    sicaklik = random.uniform(20, 35)
    nem = random.uniform(30, 70)
    ruzgar_hizi = random.uniform(5, 40)
    yagis_7_gun = random.uniform(0, 30)
    
    return {
        'sicaklik': round(sicaklik, 1),
        'nem': round(nem, 1),
        'ruzgar_hizi': round(ruzgar_hizi, 1),
        'yagis_7_gun': round(yagis_7_gun, 1)
    }

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

def process_geojson_with_test_data():
    """
    GeoJSON dosyasını test verileriyle işleyip her alan için risk hesaplama
    """
    print("GeoJSON dosyası test verileriyle işleniyor...")
    
    # GeoJSON dosyasını oku
    with open('static/export.geojson', 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    print(f"Toplam {len(geojson_data['features'])} alan bulundu.")
    
    # Her feature için risk hesapla
    for i, feature in enumerate(geojson_data['features']):
        print(f"İşleniyor: {i+1}/{len(geojson_data['features'])}")
        
        # Koordinatları al
        geometry = feature['geometry']
        if geometry['type'] == 'Polygon':
            coordinates = geometry['coordinates']
        elif geometry['type'] == 'MultiPolygon':
            # MultiPolygon için ilk polygon'u al
            coordinates = geometry['coordinates'][0]
        else:
            print(f"Desteklenmeyen geometry tipi: {geometry['type']}")
            continue
        
        # Centroid hesapla
        centroid_lat, centroid_lon = calculate_centroid(coordinates)
        
        if centroid_lat is None or centroid_lon is None:
            print(f"Centroid hesaplanamadı: Feature {i}")
            continue
        
        # Test hava durumu verileri üret
        weather_data = generate_test_weather_data()
        
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
        feature['properties']['sicaklik'] = weather_data['sicaklik']
        feature['properties']['nem'] = weather_data['nem']
        feature['properties']['ruzgar_hizi'] = weather_data['ruzgar_hizi']
        feature['properties']['yagis_7_gun'] = weather_data['yagis_7_gun']
        feature['properties']['son_guncelleme'] = datetime.now().isoformat()
        feature['properties']['test_verisi'] = True  # Test verisi olduğunu belirt
        
        # Hızlı işlem için kısa bekleme
        if i % 50 == 0:
            time.sleep(0.1)
    
    # Güncellenmiş GeoJSON'u kaydet
    output_filename = f'static/export_with_risk_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.geojson'
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    
    print(f"Test risk hesaplama tamamlandı. Sonuç: {output_filename}")
    return output_filename

if __name__ == "__main__":
    process_geojson_with_test_data() 