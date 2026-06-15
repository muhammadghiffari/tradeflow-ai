import json

nb_path = r'c:\tradeflow-ai\tools\kaggle\nb4_eval.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        
        # 1. Patch load_image to resize and prevent OOM
        if 'def load_image(path_str):' in src:
            old_load = (
                "def load_image(path_str):\n"
                "    path_str = str(path_str)\n"
                "    if path_str.endswith('.pdf'):\n"
                "        pages = convert_from_path(path_str, dpi=150, first_page=1, last_page=1)\n"
                "        return pages[0].convert('RGB')\n"
                "    return Image.open(path_str).convert('RGB')\n"
            )
            new_load = (
                "def load_image(path_str, max_size=1024):\n"
                "    path_str = str(path_str)\n"
                "    if path_str.endswith('.pdf'):\n"
                "        # Gunakan DPI 100 agar lebih kecil (sebelumnya 150)\n"
                "        pages = convert_from_path(path_str, dpi=100, first_page=1, last_page=1)\n"
                "        img = pages[0].convert('RGB')\n"
                "    else:\n"
                "        img = Image.open(path_str).convert('RGB')\n"
                "    \n"
                "    # Resize untuk mencegah CUDA Out of Memory pada GPU T4\n"
                "    if max(img.size) > max_size:\n"
                "        ratio = max_size / max(img.size)\n"
                "        new_size = (int(img.width * ratio), int(img.height * ratio))\n"
                "        img = img.resize(new_size, Image.Resampling.LANCZOS)\n"
                "    return img\n"
            )
            if old_load in src:
                src = src.replace(old_load, new_load)
                cell['source'] = list(map(lambda l: l if l.endswith('\n') else l, src.splitlines(keepends=True)))
                print("Patched load_image to prevent OOM")

        # 2. Add torch.cuda.empty_cache() to predict_document
        if 'def predict_document' in src and 'torch.cuda.empty_cache()' not in src:
            old_pred = (
                "    except:\n"
                "        return {}\n"
            )
            new_pred = (
                "    except:\n"
                "        res = {}\n"
                "    finally:\n"
                "        del inputs, generated_ids, generated_ids_trimmed\n"
                "        import gc; gc.collect()\n"
                "        torch.cuda.empty_cache()\n"
                "    return res\n"
            )
            # Find the return inside try:
            src = src.replace("return json.loads(match.group(0))", "res = json.loads(match.group(0))")
            src = src.replace("return json.loads(output_text)", "res = json.loads(output_text)")
            src = src.replace(old_pred, new_pred)
            cell['source'] = list(map(lambda l: l if l.endswith('\n') else l, src.splitlines(keepends=True)))
            print("Patched predict_document to add CUDA cache clearing")

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("nb4 patched to prevent CUDA OOM")
