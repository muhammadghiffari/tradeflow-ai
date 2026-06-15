import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb3_olm_finetune.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = cell['source']
        if 'class Qwen2VLDataCollator:' in ''.join(src):
            new_src = []
            for line in src:
                if 'truncation=True,' in line or 'max_length=2048,' in line:
                    continue
                new_src.append(line)
            cell['source'] = new_src

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Removed truncation from Qwen2VLDataCollator.")
