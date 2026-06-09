# 問題数バリデーション(投入時)

このドキュメントは, 投入時に検証される **期待問題数** をまとめたものだよ.

ペイロードがこの期待値と一致しない場合, APIはHTTP 422で次の形式を返す.

```json
{"status":"error","errors":["...message..."]}
```

## 模擬試験(full mock) (`/import/full_mock`)

### Listening
- `listening_part_a.items`: **30**
- `listening_part_b.items`: **8**
- `listening_part_c.items`: **12**

### Grammar(Structure)
- `grammar_part_a.questions`: **15**
- `grammar_part_b.questions`: **25**

### Reading
- `reading.passages`: **5**
- `reading.passages[*].questions`: **各passage 10問** (合計 **50**)

## 実力診断(diagnostics) (`/import/diagnostics`)

### Listening
- `listening_part_a.items`: **8**
- `listening_part_b.items`: **8**
- `listening_part_c.items`: **8**

### Grammar(Structure)
- `grammar_part_a.questions`: **8**
- `grammar_part_b.questions`: **8**

### Reading
- `reading.passages`: **2**
- `reading.passages[*].questions`: **各passage 10問**

## セクション別練習(practice) (`/import/practice`)

### Listening
- `listening_part_a.items`: **10**
- `listening_part_b.items`: **4**
- `listening_part_c.items`: **4**

### Grammar(Structure)
- `grammar_part_a.questions`: **10**
- `grammar_part_b.questions`: **10**

### Reading
- `reading.passages`: **1**
- `reading.passages[1].questions`: **10**

## 正常パターン / 異常パターン(よくある原因)

投入時バリデーションは大きく次の観点で落ちるよ.

### 比較項目(チェック観点)
- **JSONとして読めるか**: ファイル全体が純粋なJSONになってるか.
- **トップレベル構造**: Listeningは `items` , Grammarは `questions` , Readingは `passages` を持つdictか.
- **期待件数**: `items/questions/passages` の件数が上の期待値と一致してるか.

### Reading の question_text (セクション / FM / 実力診断共通)
- **禁止**: 文字列に **`in line`** を部分文字列として含めない (HTTP 422 で弾く).
- **推奨**: 位置の指し示しは **`paragraph X, sentence Y`** 形式など, `in line` を使わない表現にする.
- **マーカー整合**: `question_text` に **`[Un]…[/Un]`** または **`[Vn]…[/Vn]`** がある場合, 同じ passage の本文文字列に **`[Un]正規化後の語句[/Un]`**（または V）がそのまま含まれていること (問題側で `"語"` と引用されていても本文側はタグ内をクォート無しで揃える想定).

### 正常パターン
- **先頭が `{` で始まる**(Markdownや余計な文字が入ってない).
- **JSONとしてパースできる**(カンマ/クオート/括弧が壊れてない, JSONが連結されてない).
- **想定キーが存在する**:
  - Listening: `items` がlist
  - Grammar: `questions` がlist
  - Reading: `passages` がlist, かつ `passages[*].questions` がlist
- **件数が期待通り**(このmdの表の通り).

### 異常パターン(異常項目)
以下は, 実データで発生していた異常カテゴリだよ.

#### 1) 件数不一致(内容はJSONとして正常)
- **症状**: JSONは読めるが, `items/questions` の数が期待と違う.
- **よくある例**: セクション別Listeningが 10/4/4 のはずなのに 12/8/8 になってる.
- **直し方(手動)**: 余分な問題を削る, 別ファイルに分割する, 期待値側の仕様を見直す.

#### 2) UTF-8 BOM付きでパース失敗
- **症状**: `Unexpected UTF-8 BOM` で落ちる(中身はJSONでも, 先頭にBOMが付いてる).
- **直し方(手動)**: エンコーディングを `UTF-8 (BOMなし)` で保存し直す.

#### 3) Markdownのコードフェンス混入
- **症状**: 先頭が ```json で始まるなど, JSON以外の文字が混ざって落ちる.
- **直し方(手動)**: 先頭/末尾のコードフェンス(````...````)を削除して, `{...}` だけ残す.

#### 4) JSONが複数連結(Extra data)
- **症状**: `Extra data` で落ちる(1ファイルにJSONが2つ以上連結されている).
- **直し方(手動)**: 正しいJSONだけ残す, もしくはファイルを分割して1ファイル=1JSONにする.

#### 5) JSON構文エラー(カンマ欠落, クオート未エスケープなど)
- **症状**: `Expecting ',' delimiter` などで落ちる.
- **よくある例**: Readingの `question_text` など文字列中に `[V1]"word"[/V1]` のような `"` が入って, JSON文字列が壊れる.
- **直し方(手動)**: `"` を `\\\"` にエスケープする, 欠けているカンマを補う.

