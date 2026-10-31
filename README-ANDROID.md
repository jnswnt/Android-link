# Android Link — preview awal

Adaptasi Android dari [iPhone Link oleh Kelvin Daniyar](https://github.com/kelvindaniyar/iphone-link), dengan palet, tipografi, permukaan acrylic, ikon sementara, dan pola panel pengaturan dari frontend asli. Lisensi dan atribusi upstream dipertahankan. Kode iPhone tetap tersedia secara terpisah.

## Jalankan di Windows

1. Pasang Python 3.10+, [scrcpy resmi](https://github.com/Genymobile/scrcpy/releases), dan [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools).
2. Tambahkan direktori `scrcpy.exe` dan `adb.exe` ke PATH, atau gunakan opsi path di bawah. Gunakan scrcpy modern yang mendukung `--audio-dup`.
3. Aktifkan USB debugging, hubungkan HP, dan setujui otorisasi komputer.
4. Dari root repository:

```powershell
python -m pip install pywebview
python -m handset.android
```

Alternatif tanpa pywebview (UI di browser):

```powershell
python -m handset.android --browser
```

Path eksplisit:

```powershell
python -m handset.android --adb "C:\Tools\scrcpy\adb.exe" --scrcpy "C:\Tools\scrcpy\scrcpy.exe"
```

Dependensi `pymobiledevice3`, driver Apple, dan Bluetooth Audio Sink tidak diperlukan oleh jalur Android. Entry point iPhone lama belum diubah; jangan menggunakan launcher `.bat` iPhone untuk menjalankan versi Android.

## Yang berfungsi

- Deteksi perangkat ADB, termasuk status unauthorized/offline.
- Mulai/hentikan scrcpy; video dan input mouse/keyboard melalui **jendela scrcpy terpisah**.
- Toolbar Back, Home, Recent, Volume +/−, Power (toggle tombol power), dan screenshot.
- Tujuan audio HP saja (`--no-audio`), PC saja (`--require-audio`), HP + PC (`--audio-dup`, Android 13+).
- Preset ukuran maksimum/FPS/bitrate serta layar fisik mati saat mulai.
- Restart sesi untuk menerapkan audio/kualitas; pengaturan tersimpan terpisah dari status sesi.
- Tema terang/gelap dan panel yang dapat ditutup; layout menyesuaikan layar kecil.

Audio PC memerlukan Android 11+; pada Android 11 buka kunci HP sebelum memulai. Audio duplikat mengikuti pembatasan capture masing-masing aplikasi. Status UI menyatakan proses scrcpy berjalan dan opsi yang dikirim, bukan bukti bahwa audio benar-benar terdengar. Jika proses keluar, pesan log ditampilkan.

Screenshot dan log sesi terakhir disimpan di `Pictures/Android Link` pada home pengguna. Setelah menutup jendela video, status akan diperbarui pada polling berikutnya. Menutup desktop UI atau Ctrl+C pada mode browser menghentikan sesi. Pada mode browser, menutup tab saja tidak menghentikan server; gunakan Ctrl+C pada terminal.

## Batas tahap ini

Video belum tertanam dalam toolbar. Belum ada file manager, OCR Android, recording melalui toolbar, notifikasi, auto-unlock, atau UI pairing Wi-Fi. Perangkat yang sudah tersambung via ADB Wi-Fi dapat muncul dalam daftar, tetapi alur koneksi tahap ini berfokus pada USB. Tidak ada klaim fitur tersebut sudah diimplementasikan.

## Struktur dan keamanan lokal

- `handset/android.py`: adapter dan HTTP server khusus Android, bind loopback pada port dinamis.
- `handset/web/android.*`: entry point frontend Android, memakai `app.css` asli.
- Tidak memuat `app.js`/`mirror.js` iPhone atau menyimpan PIN.
- POST memerlukan token sesi acak serta pemeriksaan Host/Origin; perintah ADB menggunakan daftar aksi tetap dan argumen subprocess, bukan shell.
- `main` tidak perlu digabung sebelum perubahan ditinjau. Target lanjutan: renderer video tertanam dan integrasi input/audio yang diuji di Windows dengan HP fisik.

## Validasi

```powershell
python -m unittest discover -s tests -v
node --check handset/web/android.js
```

Pengujian otomatis memeriksa pemilihan audio, validasi perangkat, restart invalid, daftar perintah, dan proteksi HTTP lokal. Pengujian dengan HP Android, audio nyata, dan pywebview Windows tetap diperlukan.
