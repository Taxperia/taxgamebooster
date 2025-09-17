# PulseBoost (Windows)

Hepsi bir arada Windows performans ve oyun yardımcı uygulaması.

Özellikler (MVP):
- Sistem izleme: CPU, RAM, NVIDIA GPU (NVML)
- Modern arayüz (PySide6), Tray simgesi
- Windows ile başlat seçeneği
- Temp ve Prefetch temizliği
- Otomatik güç planı geçişi (yükte Yüksek Performans)
- Ekran görüntüsü
- Ekran kaydı (dxcam + ffmpeg) — NVENC/QSV desteği
- Anında yeniden oynat (segment bazlı, ffmpeg concat)
- Başlangıç programları listeleme/devre dışı bırakma

Planlanan:
- Oyun başlatıcı modu + overlay (RTSS entegrasyonu)
- PresentMon ile FPS ölçümü
- CPU/GPU stres testi (benchmark)
- İnternet hız testi UI
- Gereksiz servisleri durdurma (güvenli beyaz liste ile)
- Arka plan süreçlerini askıya alma (whitelist + güvenlik önlemleri)
- 10 dil + çoklu tema

## Kurulum

1) Python 3.11+ ve pip kurulu olmalı.
2) Bağımlılıklar:
```bash
pip install -r requirements.txt
```
3) ffmpeg kurun ve PATH'e ekleyin:
- Windows için https://www.gyan.dev/ffmpeg/builds/ adresinden `ffmpeg-git-full` zip indirin, `ffmpeg.exe` PATH'te olmalı.

4) Çalıştır:
```bash
python app.py
```

Notlar:
- Yönetici gerektiren işlemler için UAC isteği çıkabilir.
- NVIDIA GPU metrikleri için `pynvml` ve NVIDIA sürücüleri gerekir.
- Instant Replay için Windows 10+ ve `ddagrab` önerilir; çalışmazsa `set FF_USE_GDI=1` ile `gdigrab` kullanabilirsiniz (daha yüksek CPU).

## Paketleme (PyInstaller örneği)
```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name PulseBoost app.py
```
`--add-data` ile locale/tema dosyalarını eklemeyi unutmayın.

## Güvenlik ve Sorumluluk
- Servis durdurma, süreç askıya alma gibi işlemler stabiliteyi etkileyebilir. Varsayılan olarak kapalıdır ve kullanıcının açık onayı gerekir.
- Prefetch temizliği sistemin yeniden optimizasyonuna ihtiyaç duyar; gereksiz kullanım önerilmez. Bu özellik kullanıcı talebiyle ve bilgilendirerek yapılır.
