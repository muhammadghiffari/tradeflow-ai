# ☁️ TradeFlow AI — 24/7 Free Cloud Deployment Guide

Panduan ini ditujukan bagi juri atau publik yang ingin mencoba TradeFlow AI kapan saja (24/7) tanpa perlu menjalankan Docker lokal atau menyalakan laptop yang memiliki GPU.

Arsitektur ini menggunakan **Mode Fallback**, di mana backend TradeFlow AI akan mem-bypass `olm-inference` (model 7B lokal) dan secara cerdas mendelegasikan tugas OCR ekstraksi ke **Google Gemini API** (Gratis). 

Dengan begini, Backend Anda bisa berjalan di RAM sekecil 512MB (Render.com) sementara Frontend berada di Vercel.

> [!WARNING]
> **Penilaian Juri & Arsitektur Multi-Agent:**
> Perlu diperhatikan bahwa mode 24/7 Cloud ini sengaja mematikan fitur **Multi-Agent Orchestration** (Surya, PaddleOCR, Azure DI) dan tidak memanggil model *fine-tuned* **`olmOCR-2-7B-CIPL`** karena keterbatasan hardware gratis. 
> Untuk membuktikan kepada Juri bahwa algoritma orkestrasi Anda dan model *fine-tuning* benar-benar berfungsi, Anda **WAJIB** menunjukkan hasil *Run Locally (Docker)* di laptop ber-GPU, atau memandu mereka melihat dokumentasi/video demo lokal Anda!

---

## Prasyarat Akun (Semuanya Gratis)
Anda perlu membuat akun di 3 layanan berikut jika belum punya:
1. [Render.com](https://render.com) (Untuk Backend)
2. [Supabase.com](https://supabase.com) (Untuk Database PostgreSQL & Storage)
3. [Vercel.com](https://vercel.com) (Untuk Frontend)
4. [Google AI Studio](https://aistudio.google.com/app/apikey) (Dapatkan API Key Gemini)

---

## Langkah 1: Setup Database (Supabase)
1. Buat Project baru di Supabase.
2. Buka menu **Project Settings -> Database**, salin **Connection String URI** (ubah bagian `[YOUR-PASSWORD]` dengan password saat membuat project). Ini adalah `DATABASE_URL` Anda.
3. Buka menu **Project Settings -> API**, salin `Project URL` (ini adalah `SUPABASE_URL`), `anon public` key, dan `service_role` key.
4. Buka menu **Storage**, buat satu *Bucket* baru dengan nama `tradeflow-documents` dan atur menjadi *Public*.

---

## Langkah 2: Deploy Backend (Render.com)
Karena backend ini ringan di mode Cloud, Render Free Tier sangat cukup!

1. Di Dasbor Render, klik **New -> Web Service**.
2. Pilih opsi **Build and deploy from a Git repository**. Hubungkan ke repository GitHub Anda (`tradeflow-ai`).
3. Di bagian **Root Directory**, isi dengan `apps/api`.
4. Pilih *Environment*: **Python 3**.
5. *Build Command*: `pip install -r requirements.txt`
6. *Start Command*: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
7. Masukkan **Environment Variables** (Sangat Penting):
   - `CLOUD_LLM_ONLY` = `true` *(Ini yang mematikan syarat GPU)*
   - `ENVIRONMENT` = `production`
   - `SECRET_KEY` = `isi-dengan-minimal-32-karakter-bebas`
   - `DATABASE_URL` = `<Connection String dari Langkah 1>`
   - `SUPABASE_URL` = `<URL dari Langkah 1>`
   - `SUPABASE_ANON_KEY` = `<Anon key dari Langkah 1>`
   - `SUPABASE_SERVICE_KEY` = `<Service role key dari Langkah 1>`
   - `SUPABASE_JWT_SECRET` = `isi-dengan-minimal-32-karakter-bebas`
   - `GEMINI_API_KEY` = `<Gemini API Key Anda>`
8. Klik **Create Web Service**. Tunggu hingga deploy selesai dan catat URL publiknya (misal: `https://tradeflow-api-xyz.onrender.com`).

---

## Langkah 3: Deploy Frontend (Vercel)
Terakhir, kita mengarahkan Frontend ke Backend Render Anda.

1. Di Dasbor Vercel, klik **Add New -> Project**.
2. Import repository `tradeflow-ai`.
3. Set **Root Directory** ke `apps/web`.
4. Di bagian **Environment Variables**, tambahkan:
   - `NEXT_PUBLIC_API_URL` = `<URL Render dari Langkah 2>`
5. Klik **Deploy**.

---

🎉 **SELESAI!**
Sekarang aplikasi Anda memiliki *URL abadi* (misal: `https://tradeflow-ai.vercel.app`) yang hidup 24/7. Anda bisa menaruh URL ini di `README.md` dan membagikannya kepada para juri AI Open 2026.

*(Bagi developer yang tetap ingin menjalankan versi lokal penuh dengan GPU dan olmOCR, cukup jalankan `docker compose up -d` seperti biasa).*
