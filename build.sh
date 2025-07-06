#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Statik dosyaların yazma izinlerini kontrol et
chmod -R 755 static/
chmod -R 755 templates/ 