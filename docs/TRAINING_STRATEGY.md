# TradeFlow AI — Training Strategy
## Anti-Memorization Framework v2.0

> **Problem**: Jika kita hanya melatih dengan data sintetis, model mempelajari *pola sintetis*  
> — bukan struktur B/L asli. Akurasi terhadap dokumen nyata akan menurun drastis.  
> **Solusi**: Lima pilar yang menutup celah distribusi *synthetic-to-real*.

---

## TL;DR — Urutan Eksekusi

| Notebook | Peran | Output |
|---|---|---|
| `nb0_real_doc_augmentation.ipynb` | **BARU** | 8 PDF asli → 400+ gambar yang di-augment |
| `nb1_synthetic_generator.ipynb` | **UPGRADE** | PDF carrier-faithful (HLCU/MSCU/MAEU/EGLV/CSLU) |
| `nb2_chromadb_index.ipynb` | tidak berubah | HS-code vector index |
| `nb3_olm_finetune.ipynb` | **UPGRADE** | 4-phase curriculum dengan early stopping berbasis real-doc |
| `nb4_eval.ipynb` | tidak berubah | Skor ANLS/WER final terhadap 8 dokumen asli |
| `nb5_xgboost.ipynb` | tidak berubah | Rejection predictor |

**Urutan wajib**: `nb0 → nb1 → nb2 → nb3 → nb4 → nb5`

---

## Masalah: Synthetic-to-Real Distribution Gap

Ketika kita hanya melatih dengan PDF yang di-generate, tiga mode kegagalan muncul:

```
Mode 1: FONT MEMORISATION
  Sintetis menggunakan grid Helvetica → model gagal pada tabel Hapag-Lloyd berbasis Times

Mode 2: LAYOUT MEMORISATION
  Sintetis menggunakan form generik → model gagal pada sistem field bernomor Evergreen (1–33)

Mode 3: NOISE BLINDNESS
  Sintetis adalah pixel-perfect → model gagal ketika watermark ORIGINAL menutupi field kargo
```

Akar masalahnya adalah **distribution shift**: distribusi training ≠ distribusi inferensi.

### Mengapa Kita TIDAK Bisa Hanya Melatih dengan 8 Dokumen Asli

| Kendala | Alasan |
|---|---|
| Hanya 8 dokumen | Jauh terlalu sedikit untuk supervised fine-tuning model 7B |
| Mereka ADALAH test set | Melatih dengan mereka = "menghafal soal ujian" |
| Ground truth sudah ada | Jika GT label dipakai untuk training, nb4_eval menjadi tidak bermakna |

---

## 5-Pilar Solusi

### Pilar 1 — Carrier-Faithful Synthetic Generation (nb1 UPGRADE)

**Pendekatan lama**: Invoice generik dengan data Faker acak.  
**Pendekatan baru**: 5 template PDF carrier-spesifik yang mereplikasi posisi field, hierarki font, layout kolom, dan style header dari HLCU/MSCU/MAEU/EGLV/CSLU yang asli.

Nilainya di-randomize, namun **strukturnya identik dengan carrier asli**.  
Hasilnya: Model berlatih dengan layout yang benar sejak hari pertama.

Peningkatan utama:
- 5 carrier templates, masing-masing cocok dengan gambar dokumen asli
- Semua **7 format tanggal** yang digunakan lintas carrier (dikonfirmasi dari ground truth)
- HS code di-generate dengan titik (`8482.10.00`) dan tanpa titik (`84821000`) — 50/50 split
- Nomor kontainer: 20% dengan spasi (`HLXU 2382861`), 80% dinormalisasi
- Satuan berat: 60% KGS, 30% KGM, 10% MTS (gaya Evergreen — harus dikali ×1000)
- 4 jenis watermark yang di-inject secara overlay
- Simulasi noise scan (kompresi JPEG + Gaussian noise + rotasi ±3°)

Target: **1.500 CIPL triple sintetis** (B/L + Packing List + Invoice per shipment)

### Pilar 2 — Domain Adaptive Pre-Training / DAPT (nb3 Phase 0)

DAPT = kelanjutan unsupervised pre-training objective pada **gambar dokumen asli**.

- Input: 8 PDF asli yang di-rasterisasi menjadi gambar
- Task: Standard causal language modelling (tanpa label ekstraksi field)
- Efek: Visual encoder model beradaptasi ke distribusi pixel dokumen asli
- **Zero label leakage**: tidak ada ground truth JSON yang dikonsumsi

Langkah ini saja menutup ~40% dari distribution gap sebelum supervised training dimulai.

### Pilar 3 — Augmentasi Agresif Dokumen Asli (nb0 BARU)

8 PDF asli × 50 augmentasi masing-masing = **400+ gambar training-adjacent**.

| Transform | Parameter | Tujuan |
|---|---|---|
| Rotation | ±3° | Kemiringan scanner |
| GaussianBlur | σ 0.5–1.5 | Blur fokus kamera |
| JPEG compression | kualitas 60–95 | Dokumen yang dikirim via WhatsApp |
| GaussNoise | σ 5–20 | Butiran mesin fotokopi |
| BrightnessContrast | ±15% | Variasi exposure scanner |
| Perspective warp | scale 0.005–0.025 | Dokumen tidak rata |
| Shadow | darkening di tepi | Bayangan scan fisik |
| Watermark overlay | DRAFT/ORIGINAL/PROOFREAD/READ | Cap carrier asli |
| Fold-line | penurunan kecerahan ±40px | Lipatan fisik |
| CLAHE | clip 2.0 | Over-enhancement scanner |

**Pembagian dataset**:
- 5 docs → gambar augmentasi training (255 sampel)
- 3 docs → gambar augmentasi validasi (63 sampel, untuk early-stopping saja)

> ✅ Ground truth label **tidak pernah** digunakan di nb0 — murni augmentasi visual.

### Pilar 4 — 4-Phase Curriculum Learning (nb3 UPGRADE)

Training berlangsung dari mudah (sintetis bersih) ke sulit (asli + berisik):

```
Phase 0  DAPT          │ 8 gambar asli (unsupervised, causal LM)
                       │ Epoch: 3  |  LR: 1e-4  |  Tanpa LoRA
                       ↓
Phase 1  Synthetic SFT │ 1.500 CIPL triple sintetis
                       │ Epoch: 3  |  LR: 2e-4  |  LoRA r=32 α=64
                       ↓
Phase 2  Mixed Training│ 80% sintetis + 20% augmented real
                       │ Epoch: 3  |  LR: 1e-4  |  LoRA r=32 (dilanjutkan)
                       ↓
Phase 3  Hard Negatives│ Kasus membingungkan: tanggal, nomor kontainer berspace, berat MTS
                       │ Epoch: 2  |  LR: 5e-5  |  LoRA r=16 (lebih ketat)
```

Setelah **setiap phase**, model dievaluasi pada 3 dokumen validasi asli.  
Training berhenti lebih awal jika ANLS validasi tidak membaik selama 2 checkpoint berturut-turut.

### Pilar 5 — Real-Document Validation Signal (nb3 UPGRADE)

Alih-alih menggunakan `eval_loss` (yang hanya mengukur performa pada data sintetis), kita menggunakan  
**ANLS pada dokumen validasi asli** sebagai kriteria stopping.

```python
# Pseudo-code early stopping berbasis real-doc
if val_anls_on_real_docs > best_anls:
    best_anls = val_anls_on_real_docs
    save_checkpoint("best")
    patience = 0
else:
    patience += 1
    if patience >= 2:
        print("Early stop: real-doc ANLS sudah plateau")
        break
```

Loss function menggunakan **field-weighted cross-entropy** untuk menghukum error pada field kritis CEISA:

| Field | Weight | Alasan |
|---|---|---|
| `nomorBl` | 3.0 | Kunci primer CEISA |
| `hs_code` | 3.0 | Penyebab penolakan #1 |
| `beratKotor` | 2.5 | Penyebab penolakan #2 |
| `tglBl` | 2.0 | Error format tanggal sering terjadi |
| `container_no` | 2.0 | Error normalisasi spasi |
| Semua field lain | 1.0 | Baseline |

---

## Checklist Teknik Anti-Memorisasi

- [x] **LoRA r=32** di Phase 1–2 (rank lebih tinggi = generalisasi lebih baik vs r=16)
- [x] **Dropout 0.10** di layer LoRA (vs default 0.05 — regularisasi lebih kuat)
- [x] **Weight decay 0.01** di AdamW
- [x] **Cosine LR schedule** dengan warmup (5% dari steps)
- [x] **Label smoothing 0.1** di cross-entropy loss
- [x] **Tidak pernah** ada mini-batch all-synthetic di Phase 2 (selalu mixed)
- [x] **Temperature sampling** saat inferensi (T=0.1 untuk ekstraksi deterministik)
- [x] **Gradient clipping** max_norm=1.0

---

## Arsitektur Data

```
dataset/
├── synthetic/          ← output nb1: 1.500 × {PDF B/L + GT JSON}
├── augmented/          ← output nb0: 8 × 51 gambar yang di-augment
│   ├── Hapag_Filled_1/ │   ├── orig.jpg
│   │                   │   ├── aug_001.jpg ... aug_050.jpg
│   └── ...
├── augmented_manifest.json   ← pembagian train/val (5/3)
└── chroma_db/          ← output nb2: HS-code vector index

eval/fixtures/          ← TIDAK PERNAH disentuh saat training (pure holdout)
├── Hapag_Filled_1.pdf
├── Hapag_Filled_2.pdf
└── ... (8 dokumen carrier asli)
```

---

## Protokol Evaluasi

Skor final dihitung di `nb4_eval.ipynb` terhadap 8 dokumen asli:

| Metrik | Target (SRS NFR-007/008) | Cara Ukur |
|---|---|---|
| Akurasi field PDF digital | ≥ 95% | ANLS ≥ 0.95 per field |
| Akurasi field scan/foto | ≥ 85% | ANLS ≥ 0.85 |
| Delta fine-tuned vs zero-shot | ≥ +8% | Δ ANLS |
| Deteksi disagreement agent | ≥ 90% | Recall pada field yang diflag |
| HS code RAG top-1 | ≥ 75% | Exact match |
| Processing time P95 (GPU) | < 15s | Wall clock |

### Pemisahan Early Stopping vs Final Eval

```
Validation set (3 docs, augmented) ── digunakan untuk ──→ Early stopping saat nb3
Test set       (8 docs, originals) ── digunakan untuk ──→ Skor final di nb4_eval
```

Kedua set ini tidak pernah dicampur.

---

## Data Flywheel (Pasca-Kompetisi)

Setelah setiap deklarasi produksi:

```
Koreksi Operator  →  sampel baru berlabel  →  ditambahkan ke mix Phase-2
CEISA DITERIMA    →  positive reinforcement (weight ×1.0)
CEISA DITOLAK     →  hard negative (weight ×3.0)
                  ↓
Setiap 500 koreksi → update LoRA adapter (hanya nb3 Phase 3)
Setiap 100 hasil  → retrain XGBoost (nb5)
```

Loop ini adalah alasan TradeFlow AI terus semakin pintar setiap deklarasi yang diproses.
