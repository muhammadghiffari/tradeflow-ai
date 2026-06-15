import json

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# TradeFlow AI — nb3_olm_finetune (v3 — Real PyTorch Training)\n",
    "\n",
    "**Model**: `allenai/olmOCR-7B-0225-preview` (Qwen2-VL architecture)\n",
    "**Tujuan**: Melatih model sungguhan dengan `SFTTrainer` dan PyTorch.\n",
    "**Perubahan v3**: \n",
    "- Menggunakan Ground Truth untuk 5 dokumen Real Train\n",
    "- Custom Data Collator untuk Multimodal Qwen2-VL\n",
    "- Menghapus `train_dapt` unsupervised (tidak kompatibel dengan SFT)\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "!pip install -q peft transformers datasets accelerate bitsandbytes trl qwen-vl-utils\n",
    "!pip install -q pdf2image pillow albumentations\n",
    "!apt-get update -qq && apt-get install -qq poppler-utils"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import json, os, math, time, gc\n",
    "import torch\n",
    "import numpy as np\n",
    "from pathlib import Path\n",
    "from PIL import Image\n",
    "from pdf2image import convert_from_path\n",
    "from datasets import Dataset\n",
    "from transformers import (\n",
    "    Qwen2VLForConditionalGeneration, \n",
    "    AutoProcessor, \n",
    "    BitsAndBytesConfig, \n",
    "    TrainingArguments, \n",
    "    Trainer\n",
    ")\n",
    "from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training\n",
    "from kaggle_secrets import UserSecretsClient\n",
    "\n",
    "MODEL_ID  = 'allenai/olmOCR-7B-0225-preview'\n",
    "OUT_DIR   = Path('./olmocr-tradeflow-lora')\n",
    "OUT_DIR.mkdir(parents=True, exist_ok=True)\n",
    "\n",
    "NB0_INPUT = Path('/kaggle/input/nb0-real-doc-augmentation')\n",
    "NB1_INPUT = Path('/kaggle/input/nb1-synthetic-generator')\n",
    "MANIFEST_PATH = NB0_INPUT / 'dataset' / 'augmented_manifest.json'\n",
    "SYNTHETIC_DIR = NB1_INPUT / 'dataset' / 'synthetic'\n",
    "GT_PATH = Path('/kaggle/input/tradeflow-real-docs/TradeFlow_GroundTruth_v5.2.json')\n",
    "\n",
    "DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'\n",
    "print(f'Device : {DEVICE}')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 1. Load Model & Processor"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "try:\n",
    "    user_secrets = UserSecretsClient()\n",
    "    hf_token = user_secrets.get_secret(\"HF_TOKEN\")\n",
    "except:\n",
    "    hf_token = None\n",
    "    print(\"Warning: HF_TOKEN not found in Kaggle Secrets.\")\n",
    "\n",
    "print(f'Loading processor dari {MODEL_ID}...')\n",
    "processor = AutoProcessor.from_pretrained(MODEL_ID, token=hf_token)\n",
    "\n",
    "quantization_config = BitsAndBytesConfig(\n",
    "    load_in_4bit=True,\n",
    "    bnb_4bit_compute_dtype=torch.float16,\n",
    "    bnb_4bit_quant_type=\"nf4\"\n",
    ")\n",
    "\n",
    "model = Qwen2VLForConditionalGeneration.from_pretrained(\n",
    "    MODEL_ID,\n",
    "    quantization_config=quantization_config,\n",
    "    device_map='auto',\n",
    "    token=hf_token\n",
    ")\n",
    "model = prepare_model_for_kbit_training(model)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 2. Dataset Preparation (Multimodal)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "def load_image(path_str):\n",
    "    if path_str.endswith('.pdf'):\n",
    "        pages = convert_from_path(path_str, dpi=150, first_page=1, last_page=1)\n",
    "        return pages[0].convert('RGB')\n",
    "    return Image.open(path_str).convert('RGB')\n",
    "\n",
    "def create_qwen_message(img_path, json_str):\n",
    "    return {\n",
    "        \"messages\": [\n",
    "            {\n",
    "                \"role\": \"user\",\n",
    "                \"content\": [\n",
    "                    {\"type\": \"image\"},\n",
    "                    {\"type\": \"text\", \"text\": \"Extract CEISA fields from this shipping document. Return JSON with: nomorBl, tglBl, pelabuhan_muat, pelabuhan_bongkar, container_no, beratKotor, hs_code.\"}\n",
    "                ]\n",
    "            },\n",
    "            {\n",
    "                \"role\": \"assistant\",\n",
    "                \"content\": [\n",
    "                    {\"type\": \"text\", \"text\": json_str}\n",
    "                ]\n",
    "            }\n",
    "        ],\n",
    "        \"image_path\": img_path\n",
    "    }\n",
    "\n",
    "gt_data = json.loads(GT_PATH.read_text()) if GT_PATH.exists() else {}\n",
    "dataset_examples = []\n",
    "\n",
    "# A. Load Augmented Real Docs (Hanya TRAIN split, butuh Ground Truth)\n",
    "if MANIFEST_PATH.exists():\n",
    "    manifest = json.loads(MANIFEST_PATH.read_text())\n",
    "    for item in manifest.get('train', []):\n",
    "        doc_id = item['doc_id']\n",
    "        if doc_id in gt_data:\n",
    "            img_path = str(item['path']).replace('./dataset', str(NB0_INPUT/'dataset'))\n",
    "            dataset_examples.append(create_qwen_message(img_path, json.dumps(gt_data[doc_id])))\n",
    "    print(f\"Loaded {len(dataset_examples)} real augmented images.\")\n",
    "\n",
    "# B. Load Synthetic Docs\n",
    "synth_count = 0\n",
    "if SYNTHETIC_DIR.exists():\n",
    "    # Batasi sampel sintetis agar tidak out of memory / terlalu lama saat tes awal\n",
    "    for json_file in list(SYNTHETIC_DIR.glob(\"*.json\"))[:300]:\n",
    "        pdf_file = json_file.with_suffix('.pdf')\n",
    "        if pdf_file.exists():\n",
    "            gt_json = json.loads(json_file.read_text())\n",
    "            dataset_examples.append(create_qwen_message(str(pdf_file), json.dumps(gt_json)))\n",
    "            synth_count += 1\n",
    "    print(f\"Loaded {synth_count} synthetic documents.\")\n",
    "\n",
    "train_dataset = Dataset.from_list(dataset_examples)\n",
    "print(f\"Total training examples: {len(train_dataset)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. Custom Data Collator untuk Qwen2-VL"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "class Qwen2VLDataCollator:\n",
    "    def __init__(self, processor):\n",
    "        self.processor = processor\n",
    "\n",
    "    def __call__(self, examples):\n",
    "        texts = []\n",
    "        images = []\n",
    "        for example in examples:\n",
    "            # Format text using chat template\n",
    "            text = self.processor.apply_chat_template(\n",
    "                example[\"messages\"], tokenize=False, add_generation_prompt=False\n",
    "            )\n",
    "            texts.append(text)\n",
    "            # Load image\n",
    "            img = load_image(example[\"image_path\"])\n",
    "            images.append(img)\n",
    "\n",
    "        # Proses batch menjadi tensor\n",
    "        batch = self.processor(\n",
    "            text=texts,\n",
    "            images=images,\n",
    "            return_tensors=\"pt\",\n",
    "            padding=True\n",
    "        )\n",
    "\n",
    "        # Buat labels untuk loss calculation (abaikan padding)\n",
    "        labels = batch[\"input_ids\"].clone()\n",
    "        labels[labels == self.processor.tokenizer.pad_token_id] = -100\n",
    "        batch[\"labels\"] = labels\n",
    "        return batch\n",
    "\n",
    "data_collator = Qwen2VLDataCollator(processor)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 4. Training Loop (SFTTrainer)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "print('=== Memulai Training Qwen2-VL ===')\n",
    "\n",
    "lora_config = LoraConfig(\n",
    "    r=16,\n",
    "    lora_alpha=32,\n",
    "    target_modules=['q_proj', 'v_proj', 'k_proj', 'o_proj'],\n",
    "    lora_dropout=0.05,\n",
    "    bias='none',\n",
    "    task_type='CAUSAL_LM'\n",
    ")\n",
    "\n",
    "model = get_peft_model(model, lora_config)\n",
    "model.print_trainable_parameters()\n",
    "\n",
    "training_args = TrainingArguments(\n",
    "    output_dir=\"./olmocr-tradeflow-lora/final\",\n",
    "    learning_rate=1e-4,\n",
    "    num_train_epochs=1,           # Gunakan 1 epoch dulu untuk uji coba Kaggle agar tidak timeout\n",
    "    per_device_train_batch_size=1,  # VRAM sangat rentan penuh\n",
    "    gradient_accumulation_steps=8,\n",
    "    warmup_ratio=0.05,\n",
    "    weight_decay=0.01,\n",
    "    logging_steps=10,\n",
    "    save_strategy=\"no\",\n",
    "    remove_unused_columns=False,  # PENTING untuk custom collator\n",
    "    fp16=True,\n",
    ")\n",
    "\n",
    "trainer = Trainer(\n",
    "    model=model,\n",
    "    args=training_args,\n",
    "    train_dataset=train_dataset,\n",
    "    data_collator=data_collator,\n",
    ")\n",
    "\n",
    "# Mulai training!\n",
    "trainer.train()\n",
    "\n",
    "print(\"Training selesai. Menyimpan model...\")\n",
    "trainer.model.save_pretrained(OUT_DIR / 'best')\n"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 5. Upload Model ke HuggingFace Hub"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "HF_REPO_NAME = 'your-org/olm-ocr-cipl-v1'  # Ganti dengan org HF Anda\n",
    "\n",
    "# Uncomment untuk mengupload hasil nyata:\n",
    "# if hf_token:\n",
    "#     from huggingface_hub import HfApi\n",
    "#     api = HfApi(token=hf_token)\n",
    "#     api.create_repo(repo_id=HF_REPO_NAME, exist_ok=True)\n",
    "#     trainer.model.push_to_hub(HF_REPO_NAME, token=hf_token)\n",
    "#     processor.push_to_hub(HF_REPO_NAME, token=hf_token)\n",
    "#     print(f'✓ Model berhasil diupload ke: https://huggingface.co/{HF_REPO_NAME}')\n"
   ]
  }
 ],
 "metadata": {
  "accelerator": "GPU",
  "colab": {
   "gpuType": "T4"
  },
  "kernelspec": {
   "display_name": "Python 3 (ipykernel)",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.10.12"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}

with open(r'c:\tradeflow-ai\tools\kaggle\nb3_olm_finetune.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)
