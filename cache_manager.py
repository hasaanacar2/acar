import json
import os
from datetime import datetime, timedelta
import logging

class CacheManager:
    def __init__(self, cache_file="analysis_cache.json"):
        self.cache_file = cache_file
        self.cache = self.load_cache()
        self.lm_analysis_running = False
        self.lm_analysis_completed = False
        
    def load_cache(self):
        """Cache dosyasını yükle"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    print(f"DEBUG: Cache dosyası yüklendi: {self.cache_file}")
                    return json.load(f)
        except Exception as e:
            print(f"Cache yükleme hatası: {e}")
        return {}
    
    def save_cache(self):
        """Cache'i dosyaya kaydet"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            print(f"DEBUG: Cache dosyası kaydedildi: {self.cache_file}")
        except Exception as e:
            print(f"Cache kaydetme hatası: {e}")
    
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
        
        # Bir sonraki 13:00'ı hesapla (LM analizi zamanı)
        next_lm_update = now.replace(hour=13, minute=0, second=0, microsecond=0)
        if now.hour >= 13:
            next_lm_update += timedelta(days=1)
        
        # Cache geçerli mi?
        return cache_time < next_lm_update
    
    def get_cached_analysis(self, lat, lon, area, landuse, name):
        """Cache'den analiz sonucu al"""
        cache_key = self.get_cache_key(lat, lon, area, landuse, name)
        
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if self.is_cache_valid(cache_entry):
                print(f"DEBUG: Cache'den analiz sonucu alındı: {cache_key}")
                return cache_entry['data']
        
        return None
    
    def cache_analysis(self, lat, lon, area, landuse, name, analysis_data):
        """Analiz sonucunu cache'e kaydet"""
        # LM analizi çalışıyorsa cache'i güncelleme
        if self.lm_analysis_running and not self.lm_analysis_completed:
            print(f"DEBUG: LM analizi çalışıyor, cache güncellenmedi: {lat}, {lon}")
            return
        
        cache_key = self.get_cache_key(lat, lon, area, landuse, name)
        
        cache_entry = {
            'timestamp': datetime.now().isoformat(),
            'data': analysis_data
        }
        
        self.cache[cache_key] = cache_entry
        self.save_cache()
        print(f"DEBUG: Analiz sonucu cache'e kaydedildi: {cache_key}")
    
    def start_lm_analysis(self):
        """LM analizi başladığını işaretle"""
        self.lm_analysis_running = True
        self.lm_analysis_completed = False
        print("DEBUG: LM analizi başlatıldı - cache güncellemeleri duraklatıldı")
    
    def complete_lm_analysis(self):
        """LM analizi tamamlandığını işaretle"""
        self.lm_analysis_running = False
        self.lm_analysis_completed = True
        print("DEBUG: LM analizi tamamlandı - cache güncellemeleri devam ediyor")
    
    def clear_expired_cache(self):
        """Süresi dolmuş cache'leri temizle"""
        # LM analizi çalışıyorsa cache temizleme
        if self.lm_analysis_running and not self.lm_analysis_completed:
            print("DEBUG: LM analizi çalışıyor, cache temizleme ertelendi")
            return
        
        expired_keys = []
        for key, entry in self.cache.items():
            if not self.is_cache_valid(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self.save_cache()
            print(f"{len(expired_keys)} adet süresi dolmuş cache temizlendi")
    
    def get_cache_stats(self):
        """Cache istatistiklerini döndür"""
        total_entries = len(self.cache)
        valid_entries = sum(1 for entry in self.cache.values() if self.is_cache_valid(entry))
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': total_entries - valid_entries,
            'lm_analysis_running': self.lm_analysis_running,
            'lm_analysis_completed': self.lm_analysis_completed
        }

# Global cache manager instance
cache_manager = CacheManager() 