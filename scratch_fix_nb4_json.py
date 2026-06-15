import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb4_eval.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if 'def predict_document' in src:
            # Fix the json parsing bug
            old_json_logic = (
                "    except:\n"
                "        res = {}\n"
            )
            
            # Since the code might have been modified by previous patches, let's just do a string replace carefully.
            # We want to replace:
            #         if match:
            #             res = json.loads(match.group(0))
            #         res = json.loads(output_text)
            # With:
            #         if match:
            #             res = json.loads(match.group(0))
            #         else:
            #             res = json.loads(output_text)
            
            # Let's find exactly how it looks right now
            old_block_1 = (
                "        if match:\n"
                "            res = json.loads(match.group(0))\n"
                "        res = json.loads(output_text)\n"
            )
            new_block_1 = (
                "        if match:\n"
                "            res = json.loads(match.group(0))\n"
                "        else:\n"
                "            res = json.loads(output_text)\n"
            )
            
            # Fallback if it was written with return instead of res=
            old_block_2 = (
                "        if match:\n"
                "            return json.loads(match.group(0))\n"
                "        return json.loads(output_text)\n"
            )
            new_block_2 = (
                "        if match:\n"
                "            res = json.loads(match.group(0))\n"
                "        else:\n"
                "            res = json.loads(output_text)\n"
            )
            
            # Also add print for raw output so the user can debug if it fails again
            if old_block_1 in src:
                src = src.replace(old_block_1, "        print(f'Raw Output: {output_text}')\n" + new_block_1)
            elif old_block_2 in src:
                src = src.replace(old_block_2, "        print(f'Raw Output: {output_text}')\n" + new_block_2)
            else:
                print("Could not find the exact JSON parsing block to replace. Here is the source:")
                print(src)
                
            cell['source'] = list(map(lambda l: l if l.endswith('\n') else l, src.splitlines(keepends=True)))

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("nb4 JSON parsing logic patched.")
