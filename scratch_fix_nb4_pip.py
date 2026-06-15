import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb4_eval.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = cell['source']
        new_src = []
        for line in src:
            # Match nb3's working pip install — NO Pillow, NO torchvision upgrades
            if '!pip install' in line and 'transformers' in line:
                new_src.append('!pip install -q -U transformers peft datasets accelerate bitsandbytes trl qwen-vl-utils rapidfuzz\n')
            else:
                new_src.append(line)
        cell['source'] = new_src

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("nb4 pip install matched to nb3's working formula (no Pillow/torchvision upgrade)")
