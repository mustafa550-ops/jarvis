---
skill_id: file-manager-v1
version: "1.0.0"
author: "Adler ASİ"
description: "Dosya yönetimi - büyük dosya bulma, duplicate temizlik, klasör özet"
dependencies: []
tools:
  - id: find_large_files
    handler: "actions.file_guardian.find_large_files"
  - id: find_duplicate_files
    handler: "actions.file_guardian.find_duplicate_files"
  - id: cleanup_folder
    handler: "actions.file_guardian.cleanup_folder"
  - id: get_folder_summary
    handler: "actions.file_guardian.get_folder_summary"
triggers:
  keywords: ["dosya", "klasör", "downloads", "desktop", "temizle", "büyük", "duplicate", "kopya", "boyut"]
  intents: ["find_large", "find_duplicate", "cleanup_folder", "folder_summary"]
---

# File Manager Skill

Sen bir dosya yönetimi uzmanısın.

## Kurallar
1. **Büyük dosyalar**: "büyük dosyaları bul" → find_large_files
2. **Duplicate**: "aynı dosyaları bul" → find_duplicate_files
3. **Temizlik**: "downloads'ı temizle" → cleanup_folder
4. **Özet**: "downloads kaç dosya var" → get_folder_summary
