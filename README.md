#🤖 Bot Kasir Telegram (Multi-Tenant)
Selamat datang di Bot Kasir Telegram! Ini adalah sebuah sistem Point of Sale (POS) lengkap yang berjalan di atas platform Telegram, dirancang untuk mengelola usaha Anda dengan mudah dan efisien. Bot ini bersifat multi-tenant, artinya setiap pengguna yang mendaftar akan memiliki database dan datanya sendiri yang sepenuhnya terpisah.


#✨ Fitur Utama

✅ Sistem Multi-Akun: Setiap pengguna memiliki data (menu, penjualan, stok) yang terpisah dan aman.

✅ Manajemen Menu & Stok: Tambah, edit, hapus, dan sesuaikan stok produk Anda dengan mudah.

✅ Pencatatan Pesanan: Buat pesanan baru atas nama pelanggan, dengan sistem keranjang belanja interaktif yang memeriksa ketersediaan stok.

✅ Nota PDF Profesional: Cetak nota/struk untuk setiap transaksi dalam format PDF yang rapi.

✅ Laporan Keuangan: Hasilkan laporan keuangan bulanan terperinci dalam format PDF, lengkap dengan rincian pendapatan dan pengeluaran harian.

✅ Manajemen Kasbon & Pengeluaran: Catat semua pengeluaran harian dan kelola utang-piutang (kasbon) dengan mudah.

✅ Keamanan: Login berbasis username/password dan token rahasia yang disimpan dengan aman.


#🚀 Instalasi & Cara Menjalankan
Tutorial ini akan memandu Anda untuk memasang dan menjalankan bot di lingkungan baru.

1. Prasyarat

Pastikan Python dan Git sudah terpasang di sistem Anda.
```
pkg update && pkg upgrade -y
```
```
pkg install git -y
```

2. Clone Repositori Ini

Buka terminal, lalu jalankan perintah ini untuk mengunduh kode.

```
git clone https://github.com/Yoochu123/bot-kasir-telegram.git
```

3. Buka Folder Proyek

```
cd bot-kasir-telegram
```

4. Siapkan File Konfigurasi (.env)

Buat salinan dari file template .env.example menjadi .env.
Untuk Windows
```
copy .env.example .env
```
Untuk Linux/macOS
```
cp .env.example .env
```
Setelah itu, buka file .env dan masukkan Token Bot rahasia Anda.

5. Install Semua Library

Perintah ini akan menginstal semua yang dibutuhkan oleh bot secara otomatis.
```
pip install -r requirements.txt
```
6. Jalankan Bot
```
python rekap.py
```
Bot Anda sekarang sudah aktif dan berjalan. Cukup kirim perintah /start di Telegram untuk memulai!
