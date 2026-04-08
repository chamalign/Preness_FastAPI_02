# Preness Content Ingestion API

問題投入・分析レポート・**問題生成 (FM / SM / P)** 用の FastAPI アプリケーション. 外部の問題生成フローからは Celery ジョブで OpenAI 等を使い模試・演習を生成し mocks / exercises に保存する. 従来どおり問題投入 API と分析ジョブも提供し, Rails は GET で同期・参照する.

---

## ディレクトリ構造

```
FastAPI/
├── README.md
├── .env.example
├── requirements.txt
├── api_config.yaml              # 生成フロー用の設定
├── speech_config.yaml           # Azure Speech 等
├── prompts/
│   └── completed/               # パート別プロンプト (.txt)
└── app/
    ├── main.py                  # FastAPI 起動・ルーター登録
    ├── api/v1/
    │   ├── exercises.py
    │   ├── mocks.py
    │   ├── analysis.py
    │   ├── generation.py        # 生成ジョブ API
    │   └── import_content.py    # 手動 import（full_parts + S3）
    ├── core/
    │   ├── config.py
    │   └── security.py
    ├── db/
    │   ├── base.py
    │   ├── session.py
    │   └── models.py            # Mock / Exercise / AnalysisJob / GenerationJob 等
    ├── schemas/
    │   ├── exercises.py
    │   ├── mocks.py
    │   ├── analysis.py
    │   ├── generation.py
    │   └── import_payload.py
    ├── services/
    │   ├── exercise_service.py
    │   ├── mock_service.py
    │   ├── analysis/
    │   │   ├── job_store.py
    │   │   ├── report_generator.py
    │   │   └── report_generator_short.py
    │   ├── generation/          # openai_client, import_pipeline, audio_upload, *_merger 等
    │   ├── speech/              # Azure Speech (Listening TTS)
    │   └── storage/             # s3_client 等
    └── workers/
        ├── celery_app.py
        ├── analysis_tasks.py
        └── generation_tasks.py  # FM / SM / P 生成タスク
```

---

## 機能一覧（入力元・出力）

### 1. 模擬試験（mocks）

| エンドポイント | 入力元 | 受け取るデータ | 出力 |
|----------------|--------|----------------|------|
| **POST** /api/v1/mocks | 外部の問題生成アプリ | `title`, `sections[]`（section_type, parts → question_sets → questions. 各問題は 4 択・正解・解説・tag 等） | 201 + `{ status, mock_id, title }`. 自 DB に保存 |
| **GET** /api/v1/mocks | Rails 等（同期用） | クエリ: `limit`, `offset`. ヘッダ: API Key | 200 + `[{ id, title }, ...]` |
| **GET** /api/v1/mocks/{mock_id} | Rails 等 | パス: `mock_id`. ヘッダ: API Key | 200 + 模試 1 件（POST と同じ形）. 未存在時は 404（本文は FastAPI 既定の `detail` 形式） |

### 2. セクション別演習（exercises）

| エンドポイント | 入力元 | 受け取るデータ | 出力 |
|----------------|--------|----------------|------|
| **POST** /api/v1/exercises | 外部の問題生成アプリ | `section_type`, `part_type`, `question_sets[]`（passage, audio_url, questions[]） | 201 + `{ status, exercise_ids, created_count }`. 自 DB に保存 |
| **GET** /api/v1/exercises | Rails 等（同期用） | クエリ: `limit`, `offset`. ヘッダ: API Key | 200 + `[{ id, section_type, part_type }, ...]` |
| **GET** /api/v1/exercises/{exercise_id} | Rails 等 | パス: `exercise_id`. ヘッダ: API Key | 200 + 演習 1 件（POST と同じ形）. 未存在時は 404（同上） |

### 3. 分析レポート（analysis jobs）

| エンドポイント | 入力元 | 受け取るデータ | 出力 |
|----------------|--------|----------------|------|
| **POST** /api/v1/analysis/jobs | Rails（Full 模試終了後） | `attempt_id`, `exam_type`, … `answers[]`, `items[]` | 202 + `{ job_id, job_type: "full", status }` |
| **POST** /api/v1/analysis/short/jobs | Rails（Short 模試） | 85 問 `items[]`, `passages` 2×10, `goal_score` null 可 等 | 202 + `{ job_id, job_type: "short", status }` |
| **GET** /api/v1/analysis/jobs/{job_id} | Rails 等（ポーリング） | パス: `job_id`. API Key | 200 + `job_type`, `status`, `result?`. full / short で `result` の形が異なる |

- 分析 API は **ANALYSIS_API_KEY**（問題投入用の CONTENT_SOURCE_API_KEY とは別）で認証する.

### 4. 問題生成ジョブ（generation）

認証は **CONTENT_SOURCE_API_KEY**（mocks / exercises と同じ）.

| エンドポイント | 入力元 | 受け取るデータ | 出力 |
|----------------|--------|----------------|------|
| **POST** /api/v1/generation/jobs | クライアント | `job_type`: `full_mock` \| `short_mock` \| `practice`, **`title` は全種別で必須**（`practice` では未使用でも送る必要あり）, `practice` のときは `part_type` 必須（listening_part_a / grammar_part_a / reading 等のいずれか） | 202 + `{ job_id, status: "queued" }` |
| **GET** /api/v1/generation/jobs/{job_id} | 同上 | パス: UUID 文字列 | `status`（queued / running / completed / failed）, 完了時 `result` に mock_id または exercise_id 等. ジョブ未存在は 404. **UUID 形式でない** と 422 になりうる |

- ワーカー内で OpenAI, 任意で Azure Speech（Listening 音声）, 任意で S3 へ音声アップロードを行う. **OPENAI_API_KEY** 未設定時は生成ジョブは失敗しうる.

### 5. 手動 import（GPT 中間形式 → 音声→S3 → DB）

認証は **CONTENT_SOURCE_API_KEY**（mocks / generation と同じ）. 生成ジョブと同じ `full_parts` / `part_data` を **同期で**受け取り, Listening は Azure Speech → S3 で URL を付与してから保存する（**FM の大量音声では数十秒かかりうる**ので LB のタイムアウトに注意）.

| エンドポイント | 受け取るデータ | 出力 |
|----------------|----------------|------|
| **POST** /api/v1/import/full_mock | `title`, `full_parts`（`listening_part_a` … `reading` の 6 キー必須） | 201 + mocks の POST と同形 |
| **POST** /api/v1/import/short_mock | 同上 | 201 + 同上 |
| **POST** /api/v1/import/practice | `part_type`, `part_data`（生成ジョブの practice と同形） | 201 + exercises の POST と同形 |

### 6. 共通・エラー

- **422** バリデーションエラー（グローバルハンドラ）: `{ "status": "error", "errors": ["<フィールドパス>: <メッセージ>", ...] }`
- **401** 認証エラー: FastAPI 既定により `{ "detail": { "status": "error", "errors": ["Unauthorized"] } }`（`Authorization: Bearer` または `X-Api-Key`）
- **404** mocks / exercises / generation ジョブ: 多くは `{ "detail": "<メッセージ>" }`. 分析ジョブ GET の未存在は `detail` がオブジェクトになる場合あり

---

## 外部 API（GPT・Azure・S3）

### OpenAI（GPT）

| 用途 | 呼び出し元の目安 |
|------|------------------|
| 分析レポートの総評・強み・課題 | `app/services/analysis/report_generator.py` の `_generate_narratives_with_gpt()`（モデル名はコード内の指定どおり, 例: **gpt-5-mini**） |
| 模試・演習の問題生成 | `app/services/generation/`（Celery `generation_tasks` から） |

- **分析**: **OPENAI_API_KEY** 未設定時、および OpenAI 呼び出しエラー（例: 429 など）時はナラティブがプレースホルダー文言になり, ジョブ自体は完了しうる.
- **問題生成**: **OPENAI_API_KEY** 必須（未設定時は失敗しうる）.
- **分析と生成の API 統一**: 分析ナラティブは現状 **Chat Completions**（`report_generator*.py`）. 問題生成は **Responses API**. 分析も Responses に寄せるリファクタは別 PR で扱う想定.

#### OpenAI トラブルシュート（生成・分析）

| 症状 | 確認すること |
|------|----------------|
| `OPENAI_API_KEY が未設定` | Celery worker を起動したシェルで `OPENAI_API_KEY` が export されているか. **ワーカー側**にキーが必要. |
| env を変えたのに反映されない | [app/core/config.py](app/core/config.py) の `get_settings()` は `@lru_cache` のため **プロセス再起動**（uvicorn / Celery worker）が必要. |
| `DuplicateNodenameWarning: celery@Mac` | 同一 Redis を見る **Celery worker が複数**起動している可能性. `pgrep -af "celery -A app.workers.celery_app"` で列挙し、開発時は 1 本にするか `celery ... -n worker1@%h` で nodename を分ける. |
| `400` / `Unsupported parameter: 'temperature'` | [api_config.yaml](api_config.yaml) の `reasoning.effort` と `temperature` の組み合わせを確認. 生成クライアントは公式の制約に合わせてパラメータを組み立てる（詳細は `api_config.yaml` 先頭コメント）. |
| `429` / `insufficient_quota` | OpenAI ダッシュボードの **課金・利用上限**. コード側のリトライでは解消しない（generation ジョブは `failed` に更新され止まる）. |
| `429` / レート制限（quota 以外） | 短い待機後の再試行が [openai_client](app/services/generation/openai_client.py) で行われうる（完全ではないため、負荷が高い場合はジョブ間隔を空ける）. |

**venv の一致**: 本番・ローカルとも、API / Celery が **同じ Python 環境**（例: 同じ `.venv-py313`）で動いているか確認する. システムの `celery` とプロジェクト venv の `celery` が混在すると依存や env がずれる.

#### OpenAI をアプリ外で切り分ける（最小 Responses 呼び出し）

同一マシン・同一 `OPENAI_API_KEY` で、プロジェクトの venv を有効化したうえで次を実行する（プロンプトはプレースホルダ）.

```bash
.venv-py313/bin/python -c "
from openai import OpenAI
c = OpenAI()
r = c.responses.create(
    model='gpt-5.2',
    input=[{'role': 'user', 'content': 'Reply with only: {\"ok\": true}'}],
    max_output_tokens=256,
    reasoning={'effort': 'low'},
)
print((r.output_text or '')[:500])
"
```

- 成功 → アプリの kwargs か [api_config.yaml](api_config.yaml) の問題に絞れる.
- `insufficient_quota` → 課金・クォータを先に解消.
- 別の 4xx → [Responses API リファレンス](https://platform.openai.com/docs/api-reference/responses/create?lang=python) とパラメータを照合.

**生成ジョブの失敗箇所**: PostgreSQL の `generation_jobs.error_message` に stem 名付きでスタックが入る. OpenAI 以外（マージ・`MockCreate` バリデーション・S3）かどうかをログと突き合わせる.

**デバッグログ**: 生成時、`LOGLEVEL=DEBUG` でワーカーを起動すると [openai_client](app/services/generation/openai_client.py) が `responses.create` 直前に **モデル名・temperature の有無・reasoning.effort 等の要約**をログ出力する（プロンプト全文・API キーは出さない）.

### Azure Speech

Listening パートの音声合成に **Azure Speech** を利用する（`app/services/speech/azure_speech.py`）. **AZURE_SPEECH_KEY** / **AZURE_SPEECH_REGION** 未設定時は音声生成をスキップする動きになる.

### AWS S3

生成した音声などを **S3** に置く場合は **AWS_ACCESS_KEY_ID**, **AWS_SECRET_ACCESS_KEY**, **S3_BUCKET**, **S3_REGION**（任意で **S3_MOCK_AUDIO_PREFIX**）を設定. 未設定時はアップロードをスキップ.

---

## データの流れ（概要）

```
[問題生成ジョブ] --POST /api/v1/generation/jobs--> FastAPI --generation_jobs + Celery
                                                           --> Worker: OpenAI + (任意) Azure Speech + (任意) S3
                                                           --> mocks / exercises へ保存

[問題生成アプリ]  --POST (模試/演習 JSON)-->  FastAPI  --保存-->  PostgreSQL (mocks / exercises)
[Rails]           --GET (一覧・1 件)------>  FastAPI  --参照-->  上記 DB

[Rails (模試終了)] --POST (attempt_id, answers, items)-->  FastAPI  --ジョブ作成-->  PostgreSQL (analysis_jobs)
                                                                    --キュー投入-->  Redis → Celery Worker
                                                                                         --採点--> スコア・tag_accuracy
                                                                                         --OpenAI API（任意）--> 総評・強み・課題
                                                                                         --> 結果を analysis_jobs に保存
[Rails]           --GET (job_id)------------------------->  FastAPI  --参照-->  analysis_jobs → スコア・総評を返す
```

---

## 環境変数

| 変数名 | 用途 |
|--------|------|
| CONTENT_SOURCE_API_KEY | 問題投入・mocks/exercises 取得・**生成ジョブ**用 API Key |
| ANALYSIS_API_KEY | 分析ジョブ投入・結果取得用 API Key（別キー） |
| DATABASE_URL | PostgreSQL 接続文字列 |
| REDIS_URL | Celery ブローカー用 Redis |
| OPENAI_API_KEY | 分析ナラティブ（未設定時はプレースホルダー）・**問題生成（実質必須）** |
| GENERATION_OPENAI_API_KEY | （任意）問題生成専用キー. 未設定時は `OPENAI_API_KEY` を使用 |
| ANALYSIS_OPENAI_API_KEY | （任意）分析レポート専用キー. 未設定時は `OPENAI_API_KEY` を使用 |
| GENERATION_PROMPTS_DIR | （任意）プロンプト .txt ディレクトリ. 未指定時はリポジトリの `prompts/completed`（`.env.example` に無くても既定で動く） |
| AZURE_SPEECH_KEY / AZURE_SPEECH_REGION | （任意）Listening 音声合成 |
| AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET, S3_REGION | （任意）音声などの S3 アップロード |
| S3_MOCK_AUDIO_PREFIX | （任意）S3 上のプレフィックス. 既定 `mocks/audio` |
| DRY_RUN | （任意）`true` のとき **CONTENT_SOURCE_API_KEY / ANALYSIS_API_KEY が空でも** Settings が通る（ローカルで uvicorn をキー無しで起動する場合など） |

---

## 起動方法

1. `.env` に上記を設定し, PostgreSQL と Redis を起動する.
2. API: `uvicorn app.main:app --reload`
3. ワーカー: `celery -A app.workers.celery_app worker --loglevel=info`（分析タスクと生成タスクの両方が含まれる）

起動時 `init_db()` で SQLAlchemy 登録モデルに対応するテーブル（**analysis_jobs**, **generation_jobs**, mocks / exercises 系など）が存在しなければ作成される.

---
## 本番運用コマンド（手動検証・Rails連携）

### 0) 前提（変数）

```bash
export BASE_URL="http://127.0.0.1:8000"
export CONTENT_SOURCE_API_KEY="(CONTENT_SOURCE_API_KEY)"
export ANALYSIS_API_KEY="(ANALYSIS_API_KEY)"
```

ヘッダの使い分け:
- mocks / exercises / generation / import は `CONTENT_SOURCE_API_KEY`（`X-Api-Key: ...` or `Authorization: Bearer ...`）
- analysis は `ANALYSIS_API_KEY`（`Authorization: Bearer ...` が基本）

### 1) 疎通（最初に確認）

```bash
curl -sS "$BASE_URL/api/v1/mocks" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
```

### 2) 問題生成ジョブ（GPT生成 → mocks/exercises保存）

#### FM（full_mock）
```bash
curl -sS -X POST "$BASE_URL/api/v1/generation/jobs" \
  -H "Authorization: Bearer $CONTENT_SOURCE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title":"FMタイトル","job_type":"full_mock"}'
```

#### SM（short_mock）
```bash
curl -sS -X POST "$BASE_URL/api/v1/generation/jobs" \
  -H "Authorization: Bearer $CONTENT_SOURCE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title":"SMタイトル","job_type":"short_mock"}'
```

#### P（practice, part_type指定）
```bash
curl -sS -X POST "$BASE_URL/api/v1/generation/jobs" \
  -H "Authorization: Bearer $CONTENT_SOURCE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title":"P用タイトル","job_type":"practice","part_type":"listening_part_a"}'
```

完了ポーリング（job_id を差し替え）:
```bash
curl -sS "$BASE_URL/api/v1/generation/jobs/$JOB_ID" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
```

完了後, `result` から取得:
- full_mock / short_mock → `result.mock_id`
- practice → `result.exercise_ids[0]`（複数が返る可能性あり）

Railsが読む GET:
```bash
curl -sS "$BASE_URL/api/v1/mocks/$MOCK_ID" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
curl -sS "$BASE_URL/api/v1/exercises/$EXERCISE_ID" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
```

### 3) 手動 JSON 投入（外部 JSON → S3 URL付与 → mocks/exercises保存）

クライアント/外部側で用意した **中間形式**（FM/SM は `full_parts`, P は `part_data`）を投入する場合は, 既存の `/api/v1/mocks` / `/api/v1/exercises` へ直投入せず, 以下の `import` エンドポイントを使う.

この `import` は Listening の `items[].content.listening_script` を元に Azure Speech→S3 で URL を付与し, その後 DB（mocks/exercises）に保存する.

#### FM（full_mock）
```bash
curl -sS -X POST "$BASE_URL/api/v1/import/full_mock" \
  -H "Authorization: Bearer $CONTENT_SOURCE_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary "@/絶対パス/full_parts_FM.json"
```

#### SM（short_mock）
```bash
curl -sS -X POST "$BASE_URL/api/v1/import/short_mock" \
  -H "Authorization: Bearer $CONTENT_SOURCE_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary "@/絶対パス/full_parts_SM.json"
```

#### P（practice）
```bash
curl -sS -X POST "$BASE_URL/api/v1/import/practice" \
  -H "Authorization: Bearer $CONTENT_SOURCE_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary "@/絶対パス/part_data_P_listening_part_a.json"
```

Railsが読む GET:
```bash
curl -sS "$BASE_URL/api/v1/mocks/$MOCK_ID" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
curl -sS "$BASE_URL/api/v1/exercises/$EXERCISE_ID" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
```

#### hand_made txt 投入（CLI）
`hand_made/**/*.txt` から `full_parts` / `part_data` を組み立て、`/api/v1/import/*` へ直投入する。

FM（full_mock）:
```bash
python scripts/hand_made.py --api-key "$CONTENT_SOURCE_API_KEY" import-full-mock
```
`hand_made/Full_Mock_02` のようにインクリメントしたセットも投入したい場合は `set_dir` を指定する:
```bash
python scripts/hand_made.py --api-key "$CONTENT_SOURCE_API_KEY" import-full-mock "hand_made/Full_Mock_02"
```

SM（short_mock）:
```bash
python scripts/hand_made.py --api-key "$CONTENT_SOURCE_API_KEY" import-short-mock
```
`Short_Mock_02` なども同様に `set_dir` を指定:
```bash
python scripts/hand_made.py --api-key "$CONTENT_SOURCE_API_KEY" import-short-mock "hand_made/Short_Mock_02"
```

P（practice）: ファイル指定
```bash
python scripts/hand_made.py --api-key "$CONTENT_SOURCE_API_KEY" import-practice \
  --file "hand_made/Excecise/Listening_A/01_Listening_A.txt"
```

P（practice）: Reading の未使用のみランダム投入（Short/Long の候補から選ぶ）
```bash
python scripts/hand_made.py --api-key "$CONTENT_SOURCE_API_KEY" import-practice --reading-random
```
このとき未使用判定の記録ファイルは `--used-record <パス>` で指定する（省略時は記録なし）. 必要に応じて以下を指定できる:
`--seed`（乱択の再現性）, `--used-record`（記録ファイルの場所）, `--allow-all-if-exhausted`（未使用が尽きた場合でも投入を続行）

投入後の確認（レスポンスから `mock_id` / `exercise_ids` を使う）:
```bash
curl -sS "$BASE_URL/api/v1/mocks/$MOCK_ID" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
curl -sS "$BASE_URL/api/v1/exercises/$EXERCISE_ID" -H "X-Api-Key: $CONTENT_SOURCE_API_KEY"
```

注意（手動投入でハマりやすい点）:
- `curl -d @file.json` で `No such file` / `option -d: error encountered when reading a file` になる場合は, **パスが存在しない**ため, `--data-binary "@/絶対パス/...json"` を使う.
- S3 URL は Azure Speech + S3 が設定されているときのみ付与される（未設定なら URL が入らない/空になりうる）.

### 4) 分析レポート（Rails → job投入 → ポーリング）

#### Full
```bash
curl -sS -X POST "$BASE_URL/api/v1/analysis/jobs" \
  -H "Authorization: Bearer $ANALYSIS_API_KEY" \
  -H "Content-Type: application/json" \
  -d @analysis_full_payload.json
```

#### Short
```bash
curl -sS -X POST "$BASE_URL/api/v1/analysis/short/jobs" \
  -H "Authorization: Bearer $ANALYSIS_API_KEY" \
  -H "Content-Type: application/json" \
  -d @analysis_short_payload.json
```

結果取得:
```bash
curl -sS "$BASE_URL/api/v1/analysis/jobs/$JOB_ID" -H "X-Api-Key: $ANALYSIS_API_KEY"
```

### 5) 取捨選択（今回見えたエラーの扱い）

- `option -d: error encountered when reading a file`
  - 原因: curl から参照している JSON ファイルが見つからない（パス/存在確認ミス）
  - 対処: `--data-binary "@/絶対パス/...json"` に統一
- `run_analysis_report() got an unexpected keyword argument 'output_root'`
  - 原因: Celery に残っている古い/不整合なタスク引数により worker が落ちる（API/worker のバージョン不一致や, 以前に投入されたキューの残骸の可能性）
  - 対処: 本番では **API/worker を同じコードで揃えて再起動し, 新規に analysis を投入し直す**（古いジョブを再処理しない）

---

## 詳細仕様

スキーマ定義は `app/schemas/` 配下の各 `.py` を参照.
