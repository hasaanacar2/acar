import requests
import json
from datetime import datetime

# WeatherAPI.com API anahtarı
WEATHERAPI_KEY = "ca1b321f6c3948438c8181905250607"

def get_antalya_weather_data():
    """
    Antalya ili için detaylı hava durumu verilerini çeker
    """
    print("Antalya ili için hava durumu verileri çekiliyor...")
    
    # Antalya'nın farklı bölgeleri için koordinatlar
    antalya_regions = {
        "Merkez": {"lat": 36.8969, "lon": 30.7133},
        "Kemer": {"lat": 36.5971, "lon": 30.5605},
        "Alanya": {"lat": 36.5441, "lon": 31.9997},
        "Manavgat": {"lat": 36.7867, "lon": 31.4433},
        "Kaş": {"lat": 36.2017, "lon": 29.6386},
        "Finike": {"lat": 36.2997, "lon": 30.1453},
        "Elmalı": {"lat": 36.7408, "lon": 29.9175},
        "Gündoğmuş": {"lat": 36.8133, "lon": 31.9983},
        "Akseki": {"lat": 37.0483, "lon": 31.7833},
        "Gazipaşa": {"lat": 36.2667, "lon": 32.3167},
        "Korkuteli": {"lat": 37.0667, "lon": 30.1833},
        "Serik": {"lat": 36.9167, "lon": 31.1000},
        "Kumluca": {"lat": 36.3667, "lon": 30.2833},
        "Demre": {"lat": 36.2333, "lon": 29.9833},
        "İbradı": {"lat": 37.1000, "lon": 31.6000}
    }
    
    weather_data = {}
    
    for region_name, coords in antalya_regions.items():
        try:
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                'key': WEATHERAPI_KEY,
                'q': f"{coords['lat']},{coords['lon']}",
                'aqi': 'no'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                current = data['current']
                location = data['location']
                
                weather_info = {
                    'sicaklik': current['temp_c'],
                    'nem': current['humidity'],
                    'ruzgar_hizi': current['wind_kph'],
                    'yagis_7_gun': 0,  # Basitlik için 0
                    'koordinatlar': {
                        'lat': coords['lat'],
                        'lon': coords['lon']
                    },
                    'sehir': location['name'],
                    'ulke': location['country'],
                    'zaman': current['last_updated']
                }
                
                weather_data[region_name] = weather_info
                print(f"✅ {region_name}: {weather_info['sicaklik']}°C, {weather_info['nem']}% nem, {weather_info['ruzgar_hizi']} km/h rüzgar")
                
            else:
                print(f"❌ {region_name}: API hatası")
                
        except Exception as e:
            print(f"❌ {region_name}: Hata - {str(e)}")
    
    # Verileri JSON dosyasına kaydet
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"antalya_weather_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(weather_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 Veriler kaydedildi: {filename}")
    print(f"📊 Toplam {len(weather_data)} bölge için veri alındı")
    
    return weather_data

def analyze_risk_variations(weather_data):
    """
    Risk değişimlerini analiz eder
    """
    print("\n🔍 Risk Değişim Analizi:")
    print("=" * 50)
    
    sicakliklar = [data['sicaklik'] for data in weather_data.values()]
    nemler = [data['nem'] for data in weather_data.values()]
    ruzgarlar = [data['ruzgar_hizi'] for data in weather_data.values()]
    
    print(f"🌡️ Sıcaklık: {min(sicakliklar)}°C - {max(sicakliklar)}°C (Fark: {max(sicakliklar) - min(sicakliklar)}°C)")
    print(f"💧 Nem: {min(nemler)}% - {max(nemler)}% (Fark: {max(nemler) - min(nemler)}%)")
    print(f"💨 Rüzgar: {min(ruzgarlar)} km/h - {max(ruzgarlar)} km/h (Fark: {max(ruzgarlar) - min(ruzgarlar)} km/h)")
    
    # En riskli bölgeleri bul
    risk_scores = {}
    for region, data in weather_data.items():
        risk = 0
        if data['sicaklik'] >= 30: risk += 30
        elif data['sicaklik'] >= 25: risk += 25
        elif data['sicaklik'] >= 20: risk += 20
        
        if data['nem'] <= 30: risk += 25
        elif data['nem'] <= 40: risk += 20
        elif data['nem'] <= 50: risk += 15
        
        if data['ruzgar_hizi'] >= 30: risk += 25
        elif data['ruzgar_hizi'] >= 20: risk += 20
        elif data['ruzgar_hizi'] >= 10: risk += 15
        
        risk_scores[region] = risk
    
    # Risk skorlarına göre sırala
    sorted_risks = sorted(risk_scores.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n🔥 Risk Sıralaması:")
    for i, (region, risk) in enumerate(sorted_risks[:5], 1):
        data = weather_data[region]
        print(f"{i}. {region}: {risk} puan ({data['sicaklik']}°C, {data['nem']}% nem, {data['ruzgar_hizi']} km/h rüzgar)")

if __name__ == "__main__":
    weather_data = get_antalya_weather_data()
    analyze_risk_variations(weather_data) 