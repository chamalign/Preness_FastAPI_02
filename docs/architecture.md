# システムアーキテクチャ・処理フロー

## 前提

- 問題生成は **Gemini ブラウザ上で手動実行** している
- OpenAI / ChatGPT API は現時点で使用していない（`app/workers/generation_tasks.py` は未使用コードとして存在）
- 生成した問題は txt ファイルとして Google Drive に保存し、スクリプト経由で投入する

---

## 全体フロー

```mermaid
flowchart TD
    A["① Gemini ブラウザ\nprompts/*.txt を貼り付けて問題生成"] -->|".txt を Google Drive に保存"| B

    B["Google Drive\n生成済み問題/セクション別/{セクション名}/\n生成済み問題/実力診断 模擬試験/"]

    B -->|".txt 読み込み"| C

    C["② scripts/gd_import.py\ngd practice la 1\ngd mock\ngd mock --kind diag"]

    C -->|"hand_made_importer.py\ntxt → dict (payload)"| D

    D["POST /api/v1/import/practice\nPOST /api/v1/import/full_mock\nPOST /api/v1/import/diagnostics"]

    D --> E

    E["③ import_pipeline.py\n1. full_parts を outputs/ に保存\n2. build_audio_url_map\n3. build_mock/exercise_payload\n4. normalize for Rails\n5. FastAPI DB 保存\n6. Rails payload を outputs/ に保存\n7. Rails API POST"]

    E --> F[("FastAPI DB\nPostgreSQL\nmocks / exercises")]
    E --> G["Rails API\nPOST /api/v1/mocks\nPOST /api/v1/exercises\nPOST /api/v1/diagnostics"]
```

---

## 音声生成フロー（build_audio_url_map）

Listening パートのみ実行される。

```mermaid
flowchart TD
    A["listening_script (list[dict])"] --> B["_script_hash()\nsha256[:8] でハッシュ生成"]
    B --> C["S3キー決定\nmocks/audio/{part_key}/{hash}_passage.wav"]
    C --> D{"check_object_exists()\nS3 HEAD リクエスト"}
    D -->|"HIT (200)"| E["既存 URL をそのまま使用\nTTS・S3 PUT スキップ"]
    D -->|"MISS (404)"| F["Azure TTS\nsynthesize_script_to_bytes()"]
    F --> G["S3 PUT\nupload_audio_bytes()"]
    G --> H["URL を返す"]
    E --> H
```

---

## Rails DB削除時の再投入フロー

S3・TTS・Gemini は一切不要。

```mermaid
flowchart LR
    A["outputs/mock_{job_id}.json\n（生成時に自動保存済み）"] -->|"読み込み"| B["scripts/reimport.py\nmock / diagnostic / exercise"]
    B -->|"POST"| C["Rails API"]
```

コマンド一覧:

```bash
python scripts/reimport.py mock       <job_id>              # 模擬試験
python scripts/reimport.py diagnostic <job_id>              # 実力診断
python scripts/reimport.py exercise   <part_type> <job_id>  # セクション別
```

---

## 分析レポートフロー

問題投入とは独立した同期処理。

```mermaid
flowchart TD
    A["POST /api/v1/analysis/jobs"] --> B["infer_exam_type()\nparts_accuracy から full/short 判定"]
    B --> C["calculate_scores()\nセクション換算スコア計算"]
    C --> D["Gemini API\n総評・強み・課題の文面生成"]
    D --> E["post_analysis_report_to_rails()\nRails API POST"]
```

---

## 主要ファイル構成

```
FastAPI/
├── app/
│   ├── api/v1/
│   │   ├── import_content.py   # 手動投入エンドポイント (現在の主要入口)
│   │   ├── generation.py       # 自動生成エンドポイント (未使用)
│   │   ├── mocks.py            # Mock CRUD
│   │   ├── exercises.py        # Exercise CRUD
│   │   └── analysis.py         # 分析レポート
│   ├── services/
│   │   ├── hand_made_importer.py        # txt → payload 変換
│   │   ├── generation/
│   │   │   ├── import_pipeline.py       # TTS→S3→DB→Rails の中核
│   │   │   ├── audio_upload.py          # S3キャッシュ付き音声アップロード
│   │   │   └── payload_builder.py       # Mock/Exercise スキーマ組み立て
│   │   ├── speech/azure_speech.py       # Azure TTS
│   │   └── storage/s3_client.py         # S3 upload / existence check
│   ├── workers/
│   │   └── generation_tasks.py          # Celery タスク (未使用)
│   └── db/models.py                     # PostgreSQL テーブル定義
├── scripts/
│   ├── gd_import.py    # Google Drive → FastAPI 投入（メインの投入スクリプト）
│   ├── hand_made.py    # ローカル hand_made/ ディレクトリからの投入
│   └── reimport.py     # Rails DB削除後の再投入
├── prompts/            # Gemini に渡すプロンプト (.txt)
└── outputs/            # 生成済み Rails payload のバックアップ
```

---

## 環境変数

| 変数名 | 用途 |
|--------|------|
| `CONTENT_SOURCE_API_KEY` | FastAPI Bearer 認証 |
| `AZURE_SPEECH_KEY` | Azure TTS 認証 |
| `AZURE_SPEECH_REGION` | Azure TTS リージョン |
| `AWS_ACCESS_KEY_ID` | S3 認証 |
| `AWS_SECRET_ACCESS_KEY` | S3 認証 |
| `S3_BUCKET` | S3 バケット名 |
| `S3_REGION` | S3 リージョン |
| `RAILS_API_BASE_URL` | Rails 送信先 |
| `RAILS_API_KEY` | Rails Bearer 認証 |
| `DATABASE_URL` | PostgreSQL 接続先 |
