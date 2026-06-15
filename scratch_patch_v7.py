import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb3_olm_finetune.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = cell['source']
        new_src = []
        for line in src:
            if '!pip install -q peft datasets' in line:
                new_src.append('!pip install -q -U transformers peft datasets accelerate bitsandbytes trl qwen-vl-utils\n')
            elif 'AutoModelForVision2Seq' in line:
                new_src.append(line.replace('AutoModelForVision2Seq', 'Qwen2_5_VLForConditionalGeneration'))
            else:
                new_src.append(line)
        cell['source'] = new_src

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("nb3 patched to upgrade transformers and use Qwen2_5_VLForConditionalGeneration")
