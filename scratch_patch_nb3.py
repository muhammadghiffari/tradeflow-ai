"""
Patch nb3: Remove FastVisionModel.for_training() + fix manifest path + fix warmup_ratio deprecation
Root cause of error: AttributeError: 'int' has no attribute 'mean'
"""
import json

nb3_path = r'c:\tradeflow-ai\tools\kaggle\nb3_olm_finetune.ipynb'
with open(nb3_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue

    src = cell['source']
    src_str = ''.join(src)

    # --- Fix 1: Remove FastVisionModel.for_training() ---
    if 'FastVisionModel.for_training(model)' in src_str:
        new_lines = []
        for line in src:
            if 'FastVisionModel.for_training(model)' in line:
                # Replace with explanatory comment
                new_lines.append(
                    "# NOTE: FastVisionModel.for_training() DIHAPUS.\n"
                    "# Menyebabkan AttributeError: 'int' has no attribute 'mean'\n"
                    "# karena loop training Unsloth tidak kompatibel dengan custom Qwen2VLDataCollator.\n"
                    "# Unsloth tetap aktif untuk: fast loading, LoRA init, 4-bit NF4.\n"
                )
            else:
                new_lines.append(line)
        cell['source'] = new_lines
        print("[Fix 1] Removed FastVisionModel.for_training()")

    # --- Fix 2: Replace warmup_ratio (deprecated in transformers v5) ---
    if 'warmup_ratio' in src_str:
        cell['source'] = [
            line.replace(
                "    warmup_ratio=0.05,\n",
                "    warmup_steps=20,               # warmup_ratio deprecated in transformers v5\n"
            ) for line in cell['source']
        ]
        print("[Fix 2] Replaced warmup_ratio -> warmup_steps=20")

    # --- Fix 3: Add dataloader_num_workers=0 if not present ---
    if 'dataloader_num_workers' not in src_str and 'TrainingArguments' in src_str:
        cell['source'] = [
            line.replace(
                "    optim='adamw_8bit',             # Unsloth 8-bit optimizer\n",
                "    optim='adamw_8bit',             # Unsloth 8-bit optimizer\n"
                "    dataloader_num_workers=0,       # Disable multiprocessing untuk PDF loading\n"
            ) for line in cell['source']
        ]
        print("[Fix 3] Added dataloader_num_workers=0")

    # --- Fix 4: Fix manifest path resolution ---
    if 'MANIFEST NOT FOUND' not in src_str and "MANIFEST_PATH.exists()" in src_str and "img_path = str(item['path']).replace" in src_str:
        new_src = []
        skip_next = False
        for i, line in enumerate(cell['source']):
            if skip_next:
                skip_next = False
                continue
            if "img_path = str(item['path']).replace('./dataset', str(NB0_INPUT/'dataset'))" in line:
                new_src.append(
                    "            raw_path = str(item.get('path', ''))\n"
                    "            if raw_path.startswith('./dataset'):\n"
                    "                img_path = raw_path.replace('./dataset', str(NB0_INPUT / 'dataset'), 1)\n"
                    "            elif raw_path.startswith('/kaggle'):\n"
                    "                img_path = raw_path\n"
                    "            else:\n"
                    "                img_path = str(NB0_INPUT / 'dataset' / raw_path.lstrip('/'))\n"
                )
            elif "fields = gt_data[doc_id].get('ceisa_fields', gt_data[doc_id])" in line and "img_path" not in ''.join(new_src[-3:]):
                new_src.append(
                    "            if not Path(img_path).exists():\n"
                    "                print(f'  SKIP (not found): {img_path}')\n"
                    "                continue\n"
                )
                new_src.append(line)
            else:
                new_src.append(line)

        # Add fallback message after the loop
        rebuilt = []
        for line in new_src:
            rebuilt.append(line)
            if "print(f'Loaded {len(dataset_examples)} real augmented images.')" in line:
                rebuilt.append(
                    "else:\n"
                    "    print(f'MANIFEST NOT FOUND: {MANIFEST_PATH}. Only synthetic data used.')\n"
                )

        if len(rebuilt) != len(new_src):  # Only update if something changed
            cell['source'] = rebuilt
            print("[Fix 4] Fixed manifest path resolution + added fallback message")

with open(nb3_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("\nAll fixes applied to nb3_olm_finetune.ipynb")
