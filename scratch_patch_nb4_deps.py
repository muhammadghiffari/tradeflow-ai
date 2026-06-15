import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb4_eval.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = cell['source']
        new_src = []
        for line in src:
            if '!pip install -q -U transformers' in line or '!pip install -q rapidfuzz' in line:
                new_src.append('!pip install -q -U transformers Pillow torchvision rapidfuzz peft accelerate bitsandbytes qwen-vl-utils\n')
            else:
                new_src.append(line)
        cell['source'] = new_src

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("nb4 patched: added Pillow + torchvision to upgrade list")
