import json
import os
from datetime import datetime, timedelta
import logging

class CacheManager:
    def __init__(self, cache_file="analysis_cache.json"):
        self.cache_file = cache_file
        self.cache = self.load_cache()
        
    def load_cache(self):
        """Cache dosyasını yükle"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Cache yükleme hatası: {e}")
        return {}
    
    def save_cache(self):
        """Cache'i dosyaya kaydet"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Cache kaydetme hatası: {e}")
    
    def get_cache_key(self, lat, lon, area, landuse, name):
        """Cache key oluştur"""
        return f"{lat:.6f}_{lon:.6f}_{area}_{landuse}_{name}"
    
    def is_cache_valid(self, cache_entry):
        """Cache'in geçerli olup olmadığını kontrol et"""
        if not cache_entry or 'timestamp' not in cache_entry:
            return False
        
        # Şu anki zaman
        now = datetime.now()
        
        # Cache zamanı
        cache_time = datetime.fromisoformat(cache_entry['timestamp'])
        
        # Bir sonraki 12:00'ı hesapla
        next_noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now.hour >= 12:
            next_noon += timedelta(days=1)
        
        # Cache geçerli mi?
        return cache_time < next_noon
    
    def get_cached_analysis(self, lat, lon, area, landuse, name):
        """Cache'den analiz sonucu al"""
        cache_key = self.get_cache_key(lat, lon, area, landuse, name)
        
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if self.is_cache_valid(cache_entry):
                logging.info(f"Cache'den analiz sonucu alındı: {cache_key}")
                return cache_entry['data']
        
        return None
    
    def cache_analysis(self, lat, lon, area, landuse, name, analysis_data):
        """Analiz sonucunu cache'e kaydet"""
        cache_key = self.get_cache_key(lat, lon, area, landuse, name)
        
        cache_entry = {
            'timestamp': datetime.now().isoformat(),
            'data': analysis_data
        }
        
        self.cache[cache_key] = cache_entry
        self.save_cache()
        logging.info(f"Analiz sonucu cache'e kaydedildi: {cache_key}")
    
    def clear_expired_cache(self):
        """Süresi dolmuş cache'leri temizle"""
        expired_keys = []
        for key, entry in self.cache.items():
            if not self.is_cache_valid(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self.save_cache()
            logging.info(f"{len(expired_keys)} adet süresi dolmuş cache temizlendi")
    
    def get_cache_stats(self):
        """Cache istatistiklerini döndür"""
        total_entries = len(self.cache)
        valid_entries = sum(1 for entry in self.cache.values() if self.is_cache_valid(entry))
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': total_entries - valid_entries
        }

# Global cache manager instance
cache_manager = CacheManager() 