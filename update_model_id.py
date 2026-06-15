import os
from pathlib import Path

# Paths to update
files_to_update = [
    Path("c:/tradeflow-ai/docker-compose.yml"),
    Path("c:/tradeflow-ai/apps/api/src/config.py"),
    Path("c:/tradeflow-ai/apps/olm-inference/download_adapter.py"),
    Path("c:/tradeflow-ai/.env"),
    Path("c:/tradeflow-ai/.env.example"),
    Path("c:/tradeflow-ai/CLAUDE.md"),
    Path("c:/tradeflow-ai/docs/TradeFlow_PRD_v5.2.md"),
    Path("c:/tradeflow-ai/docs/TradeFlow_SDD_v5.2.md")
]

target_str = "your-org/olm-ocr-cipl-v1"
replacement_str = "muhammadghiffari/olm-ocr-cipl-v1"

print(f"Replacing '{target_str}' with '{replacement_str}'...")

for file_path in files_to_update:
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        if target_str in content:
            new_content = content.replace(target_str, replacement_str)
            file_path.write_text(new_content, encoding="utf-8")
            print(f"✅ Updated {file_path.name}")
        else:
            print(f"ℹ️ Target not found in {file_path.name}")
    else:
        print(f"⚠️ File not found: {file_path.name}")

print("Update complete!")
