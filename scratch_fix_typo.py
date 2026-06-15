import json

nb3_path = r'c:\tradeflow-ai\tools\kaggle\nb3_olm_finetune.ipynb'
with open(nb3_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('total_mem', 'total_memory')

with open(nb3_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed: total_mem -> total_memory")
