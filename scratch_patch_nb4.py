import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb4_eval.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = cell['source']
        new_src = []
        for line in src:
            # Upgrade transformers in pip install cell
            if '!pip install -q rapidfuzz' in line:
                new_src.append('!pip install -q -U transformers rapidfuzz peft accelerate pillow bitsandbytes qwen-vl-utils\n')
            # Replace AutoModelForVision2Seq with Qwen2_5_VLForConditionalGeneration
            elif 'AutoModelForVision2Seq' in line:
                new_src.append(line.replace('AutoModelForVision2Seq', 'Qwen2_5_VLForConditionalGeneration'))
            else:
                new_src.append(line)
        cell['source'] = new_src

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("nb4_eval.ipynb patched: transformers upgraded, AutoModelForVision2Seq -> Qwen2_5_VLForConditionalGeneration")
