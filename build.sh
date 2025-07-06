#!/bin/bash
echo "🚀 Build scripti başlatılıyor..."

# Python versiyonunu kontrol et
python --version

# Paketleri yükle
echo "📦 Paketler yükleniyor..."
pip install -r requirements.txt

# Test scriptini çalıştır
echo "🧪 Test scripti çalıştırılıyor..."
python test_deployment.py

echo "✅ Build tamamlandı!"

# Statik dosyaların yazma izinlerini kontrol et
chmod -R 755 static/
chmod -R 755 templates/ 