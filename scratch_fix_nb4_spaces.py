import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb4_eval.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if 'find_doc_image' in src:
            # Replace the find_doc_image function with one that handles underscore->space conversion
            old = (
                "    # Strategy 1: Look directly in real docs dataset\n"
                "    for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:\n"
                "        candidate = real_docs_dir / f'{doc_key}{ext}'\n"
                "        if candidate.exists():\n"
                "            return str(candidate)\n"
                "        # Also try lowercase\n"
                "        candidate = real_docs_dir / f'{doc_key.lower()}{ext}'\n"
                "        if candidate.exists():\n"
                "            return str(candidate)\n"
            )
            new = (
                "    # Strategy 1: Try exact match and underscore->space conversion\n"
                "    doc_key_spaced = doc_key.replace('_', ' ')  # 'Hapag_Filled_1' -> 'Hapag Filled 1'\n"
                "    for name_variant in [doc_key, doc_key_spaced, doc_key.lower(), doc_key_spaced.lower()]:\n"
                "        for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:\n"
                "            candidate = real_docs_dir / f'{name_variant}{ext}'\n"
                "            if candidate.exists():\n"
                "                return str(candidate)\n"
            )
            new_src = []
            for line in cell['source']:
                new_src.append(line)
            # Rebuild as list with replacement
            full = ''.join(cell['source'])
            full = full.replace(old, new)
            cell['source'] = [line + '\n' for line in full.split('\n') if True]
            # Simpler: just do string replace on the joined source then split back
            cell['source'] = list(map(lambda l: l if l.endswith('\n') else l, full.splitlines(keepends=True)))
            print("Patched find_doc_image with underscore->space conversion")
            break

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Done!")
