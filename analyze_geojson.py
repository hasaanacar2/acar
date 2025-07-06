import json
import math
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union

def analyze_geojson_areas():
    """
    GeoJSON dosyasındaki alanları analiz eder ve büyük alanları tespit eder
    """
    print("GeoJSON dosyası analiz ediliyor...")
    
    # GeoJSON dosyasını oku
    with open('static/export.geojson', 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    areas_info = []
    
    for i, feature in enumerate(geojson_data['features']):
        geometry = feature['geometry']
        
        if geometry['type'] == 'Polygon':
            coords = geometry['coordinates'][0]  # İlk ring (dış sınır)
            polygon = Polygon(coords)
            area = polygon.area
            centroid = polygon.centroid
            
            areas_info.append({
                'index': i,
                'type': 'Polygon',
                'area': area,
                'centroid': (centroid.x, centroid.y),
                'coordinates': coords
            })
            
        elif geometry['type'] == 'MultiPolygon':
            polygons = []
            for poly_coords in geometry['coordinates']:
                polygon = Polygon(poly_coords[0])  # İlk ring
                polygons.append(polygon)
            
            # MultiPolygon'un toplam alanını hesapla
            multi_polygon = MultiPolygon(polygons)
            area = multi_polygon.area
            centroid = multi_polygon.centroid
            
            areas_info.append({
                'index': i,
                'type': 'MultiPolygon',
                'area': area,
                'centroid': (centroid.x, centroid.y),
                'coordinates': geometry['coordinates']
            })
    
    # Alanları büyüklüğe göre sırala
    areas_info.sort(key=lambda x: x['area'], reverse=True)
    
    print(f"Toplam {len(areas_info)} alan bulundu.")
    print(f"En büyük alan: {areas_info[0]['area']:.6f}")
    print(f"En küçük alan: {areas_info[-1]['area']:.6f}")
    
    # Büyük alanları tespit et (alanın %10'undan büyük olanlar)
    threshold = areas_info[0]['area'] * 0.1
    large_areas = [area for area in areas_info if area['area'] > threshold]
    
    print(f"\nBüyük alanlar (threshold: {threshold:.6f}):")
    print("=" * 60)
    
    for i, area in enumerate(large_areas[:10], 1):
        print(f"{i}. Alan {area['index']}: {area['area']:.6f} ({area['type']})")
        print(f"   Merkez: ({area['centroid'][0]:.4f}, {area['centroid'][1]:.4f})")
        print(f"   Koordinat sayısı: {len(area['coordinates'][0]) if area['type'] == 'Polygon' else sum(len(poly[0]) for poly in area['coordinates'])}")
        print()
    
    return large_areas

def split_large_polygon(coordinates, max_area=0.001):
    """
    Büyük polygon'u daha küçük parçalara böler
    """
    if len(coordinates) < 4:
        return [coordinates]  # Çok küçükse bölme
    
    polygon = Polygon(coordinates)
    area = polygon.area
    
    if area <= max_area:
        return [coordinates]  # Yeterince küçükse bölme
    
    # Polygon'u dikdörtgen parçalara böl
    bounds = polygon.bounds
    min_x, min_y, max_x, max_y = bounds
    
    # Grid oluştur
    width = max_x - min_x
    height = max_y - min_y
    
    # Kaç parçaya böleceğimizi hesapla
    num_splits = int(math.sqrt(area / max_area)) + 1
    
    dx = width / num_splits
    dy = height / num_splits
    
    sub_polygons = []
    
    for i in range(num_splits):
        for j in range(num_splits):
            # Alt dikdörtgen oluştur
            sub_min_x = min_x + i * dx
            sub_max_x = min_x + (i + 1) * dx
            sub_min_y = min_y + j * dy
            sub_max_y = min_y + (j + 1) * dy
            
            sub_rect = Polygon([
                (sub_min_x, sub_min_y),
                (sub_max_x, sub_min_y),
                (sub_max_x, sub_max_y),
                (sub_min_x, sub_max_y)
            ])
            
            # Polygon ile kesişimini al
            intersection = polygon.intersection(sub_rect)
            
            if not intersection.is_empty:
                if isinstance(intersection, Polygon):
                    sub_polygons.append(list(intersection.exterior.coords))
                elif isinstance(intersection, MultiPolygon):
                    for poly in intersection.geoms:
                        sub_polygons.append(list(poly.exterior.coords))
    
    return sub_polygons

def create_improved_geojson():
    """
    Büyük alanları bölerek geliştirilmiş GeoJSON oluşturur
    """
    print("Geliştirilmiş GeoJSON oluşturuluyor...")
    
    # Orijinal GeoJSON'u oku
    with open('static/export.geojson', 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    
    improved_features = []
    split_count = 0
    
    for i, feature in enumerate(geojson_data['features']):
        geometry = feature['geometry']
        properties = feature.get('properties', {})
        
        if geometry['type'] == 'Polygon':
            coords = geometry['coordinates'][0]
            polygon = Polygon(coords)
            area = polygon.area
            
            # Büyük alanları böl
            if area > 0.001:  # Threshold
                sub_polygons = split_large_polygon(coords)
                split_count += len(sub_polygons)
                
                for j, sub_coords in enumerate(sub_polygons):
                    sub_centroid = Polygon(sub_coords).centroid
                    
                    improved_feature = {
                        'type': 'Feature',
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [sub_coords]
                        },
                        'properties': {
                            **properties,
                            'original_index': i,
                            'sub_index': j,
                            'centroid_lat': sub_centroid.y,
                            'centroid_lon': sub_centroid.x,
                            'area': Polygon(sub_coords).area
                        }
                    }
                    improved_features.append(improved_feature)
            else:
                # Küçük alanları olduğu gibi bırak
                centroid = polygon.centroid
                feature['properties'].update({
                    'centroid_lat': centroid.y,
                    'centroid_lon': centroid.x,
                    'area': area
                })
                improved_features.append(feature)
        
        elif geometry['type'] == 'MultiPolygon':
            # MultiPolygon'ları da böl
            for poly_coords in geometry['coordinates']:
                sub_polygons = split_large_polygon(poly_coords[0])
                split_count += len(sub_polygons)
                
                for j, sub_coords in enumerate(sub_polygons):
                    sub_centroid = Polygon(sub_coords).centroid
                    
                    improved_feature = {
                        'type': 'Feature',
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [sub_coords]
                        },
                        'properties': {
                            **properties,
                            'original_index': i,
                            'sub_index': j,
                            'centroid_lat': sub_centroid.y,
                            'centroid_lon': sub_centroid.x,
                            'area': Polygon(sub_coords).area
                        }
                    }
                    improved_features.append(improved_feature)
    
    # Geliştirilmiş GeoJSON oluştur
    improved_geojson = {
        'type': 'FeatureCollection',
        'features': improved_features
    }
    
    # Kaydet
    with open('static/export_improved.geojson', 'w', encoding='utf-8') as f:
        json.dump(improved_geojson, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Geliştirilmiş GeoJSON oluşturuldu!")
    print(f"📊 Orijinal alan sayısı: {len(geojson_data['features'])}")
    print(f"📊 Yeni alan sayısı: {len(improved_features)}")
    print(f"🔪 Bölünen alan sayısı: {split_count}")
    
    return improved_geojson

if __name__ == "__main__":
    # Önce büyük alanları analiz et
    large_areas = analyze_geojson_areas()
    
    # Sonra geliştirilmiş GeoJSON oluştur
    improved_geojson = create_improved_geojson() 