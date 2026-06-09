# 問題生成フォーマット仕様

TOEFL ITP 形式の問題生成プロンプトが出力しなければならない plain-text フォーマットの仕様書。\
対象セクション: P01–P06, FM01–FM06, SM01–SM06（計 18 セクション）。

---

## 目次

1. [共通ルール](#%E5%85%B1%E9%80%9A%E3%83%AB%E3%83%BC%E3%83%AB)

2. [Listening Part A — 短会話](#listening-part-a--%E7%9F%AD%E4%BC%9A%E8%A9%B1)

3. [Listening Part B — 長会話](#listening-part-b--%E9%95%B7%E4%BC%9A%E8%A9%B1)

4. [Listening Part C — 講義](#listening-part-c--%E8%AC%9B%E7%BE%A9)

5. [Grammar Part A — Structure（空欄補充）](#grammar-part-a--structure%E7%A9%BA%E6%AC%84%E8%A3%9C%E5%85%85)

6. [Grammar Part B — Written Expression（誤り指摘）](#grammar-part-b--written-expression%E8%AA%A4%E3%82%8A%E6%8C%87%E6%91%98)

7. [Reading](#reading)

8. [セクション別サマリー](#%E3%82%BB%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E5%88%A5%E3%82%B5%E3%83%9E%E3%83%AA%E3%83%BC)

---

## 共通ルール

### アイテムブロック構造

```
===ITEM:N===

@field_name
value

===END:N===
```

- アイテム番号 N は **1 始まりの連番**（欠番禁止）

- 各フィールドは `@field_name` を **単独行** に記述し、次の行から値が始まる

- 値が複数行にわたる場合、次の `@field_name` または `===END:N===` まで継続する

- **空の値は `null` と記述**（空行・フィールド省略は禁止）

- フィールドの過不足は禁止（指定外フィールドを追加しない、必須フィールドを省略しない）

### 出力ルール

- JSON 不可。プレーンテキスト形式のみ

- Markdown フェンス（```` ``` ````）、前置き文、ブロック外の説明文を含めない

### マーカー（Listening / Grammar セクション）

- ハイライト対象を `<< >>` で囲む。FastAPI が `[U{n}]` タグに変換する

  - 正: `The word <<it>> in line 3 refers to ...`

  - 誤: `The word [U1]it[/U1] in line 3 refers to ...`

- `<< >>` は必ずペアで使用し、ネスト禁止

### listening_script フォーマット

```
---turn---
speaker: narrator
text: Question 1.
---turn---
speaker: man
text: I'm thinking of dropping the chemistry class.
---turn---
speaker: woman
text: After all those late nights you spent on it?
---turn---
speaker: narrator
text: What does the woman imply?
```

- `---turn---` でターンを区切る（先頭ターンの前にも必要）

- `speaker:` は `man` / `woman` / `narrator` のいずれか

- `text:` は **1 行**（改行を含めない）

- 先頭ナレーター: `Question N.`

- 末尾ナレーター: `@question_text` と同一テキスト

### 説明フィールドの言語

- `@explanation` および `@wrong_reason_*` は **日本語のみ**

- 正解選択肢に対応する `@wrong_reason_*` は `null`（フィールド自体は省略不可）

---

## Listening Part A — 短会話

### フィールド一覧（P01 / FM01 / SM01 共通）

```
===ITEM:N===

@question_text
<ナレーター最終ターンと同一の質問文>

@listening_script
---turn---
speaker: narrator
text: Question N.
---turn---
speaker: <man|woman>
text: <セリフ>
---turn---
speaker: <man|woman>
text: <セリフ>
---turn---
speaker: narrator
text: <question_text と同一>

@choice_a
@choice_b
@choice_c
@choice_d
@correct_choice
<A|B|C|D>

@tag
shortConv

@explanation
<日本語>

@wrong_reason_a
<日本語 or null>
@wrong_reason_b
<日本語 or null>
@wrong_reason_c
<日本語 or null>
@wrong_reason_d
<日本語 or null>

===END:N===
```

### セクション別問題数

| セクション | モード        | 問題数 | @tag      |
|-----|----------|---|---------|
| P01   | Practice   | 12  | shortConv |
| FM01  | Full Mock  | 30  | shortConv |
| SM01  | Short Mock | 8   | shortConv |

---

## Listening Part B — 長会話

### フィールド一覧（P02 / FM02 / SM02 共通）

P01 と同一フィールド構成。`@tag` のみ異なる。

```
@tag
longConv
```

### スクリプト共有ルール

- 複数の問題が **同一スクリプトを共有**する

- 共有グループ内では `@listening_script` を逐語コピーする

### セクション別問題数・スクリプト構成

| セクション | モード        | 問題数 | スクリプト数 | 1スクリプトあたり        |
|-----|----------|---|------|----------------|
| P02   | Practice   | 8   | 2      | 4問 (Q1–4 / Q5–8) |
| FM02  | Full Mock  | 8   | 2      | 4問 (Q1–4 / Q5–8) |
| SM02  | Short Mock | 8   | 2      | 4問 (Q1–4 / Q5–8) |

---

## Listening Part C — 講義

### フィールド一覧（P03 / FM03 / SM03 共通）

P01 と同一フィールド構成。以下の点のみ異なる。

```
@tag
talk
```

### スクリプト構造

- **モノローグ形式**（講義・トーク）

- 講義部分の `speaker:` は `man` か `woman` の一方で統一（スクリプト内で混在しない）

- ナレーターは `speaker: narrator` として質問前後にのみ登場

```
---turn---
speaker: narrator
text: Questions N through M are based on the following talk.
---turn---
speaker: <man|woman>
text: <講義本文（複数ターンに分割可）>
---turn---
...
---turn---
speaker: narrator
text: Question N.
---turn---
speaker: narrator
text: <question_text と同一>
```

### セクション別問題数・スクリプト構成

| セクション | モード        | 問題数 | スクリプト数 | 1スクリプトあたり                |
|-----|----------|---|------|------------------------|
| P03   | Practice   | 8   | 2      | 4問 (Q1–4 / Q5–8)         |
| FM03  | Full Mock  | 12  | 3      | 4問 (Q1–4 / Q5–8 / Q9–12) |
| SM03  | Short Mock | 8   | 2      | 4問 (Q1–4 / Q5–8)         |

---

## Grammar Part A — Structure（空欄補充）

### フィールド一覧（P04 / FM04 / SM04 共通）

```
===ITEM:N===

@question_text
<_______ を含む文（選択肢を含まない）>

@underline_target
<question_text 中に 1 回だけ出現する下線対象文字列（必須・null 不可）>

@choice_a
@choice_b
@choice_c
@choice_d
@correct_choice
<A|B|C|D>

@tag
<verbForm|sentenceStruct|modifierConnect|nounPronoun>

@explanation
<日本語>

@wrong_reason_a
<日本語 or null>
@wrong_reason_b
<日本語 or null>
@wrong_reason_c
<日本語 or null>
@wrong_reason_d
<日本語 or null>

===END:N===
```

### 語数ルール

- 語数カウント対象: `@question_text` のみ（`_______` を含む、選択肢を含まない）

#### P04 — Practice (10問)

| Tier | 問番号    | 語数範囲   |
|----|------|------|
| 1    | Q1–Q3  | 10–16語 |
| 2    | Q4–Q6  | 15–20語 |
| 3    | Q7–Q10 | 20–28語 |

正解分布: 各文字 **max 4 個**

#### FM04 — Full Mock (15問)

| Tier | 問番号     | 語数範囲   |
|----|-------|------|
| 1    | Q1–Q5   | 10–16語 |
| 2    | Q6–Q10  | 15–20語 |
| 3    | Q11–Q15 | 20–28語 |

正解分布: 各文字 **max 4 個**（target \~4 of each）

#### SM04 — Short Mock (8問)

| Tier | 問番号   | 語数範囲   |
|----|-----|------|
| 1    | Q1–Q3 | 10–16語 |
| 2    | Q4–Q6 | 15–20語 |
| 3    | Q7–Q8 | 20–28語 |

正解分布: 各文字 **\~2 個**

---

## Grammar Part B — Written Expression（誤り指摘）

### フィールド一覧（P05 / FM05 / SM05 共通）

```
===ITEM:N===

@question_template
<{A} {B} {C} {D} プレースホルダーを含む文テンプレート>

@chunk_a
<A の下線部テキスト（複数語フレーズ可）>
@chunk_b
@chunk_c
@chunk_d

@choice_a
A
@choice_b
B
@choice_c
C
@choice_d
D

@correct_choice
<A|B|C|D（誤りのある下線部）>

@tag
<modifierConnect|verbForm|nounPronoun など>

@explanation
<日本語>

@wrong_reason_a
<日本語 or null>
@wrong_reason_b
<日本語 or null>
@wrong_reason_c
<日本語 or null>
@wrong_reason_d
<日本語 or null>

===END:N===
```

> **重要**: `@choice_a` 〜 `@choice_d` は常にリテラル文字列 `"A"` `"B"` `"C"` `"D"`（chunk の内容ではない）

### chunk ルール

- 4 つの chunk のうち **少なくとも 2 つは複数語フレーズ** であること

  - 良: `"has been"`, `"in spite of"`, `"a number of"`

  - 不可: A=`"is"`, B=`"high"`, C=`"water"`, D=`"in"` (単語のみ)

### 語数ルール

- 語数カウント: `@question_template` に `@chunk_a..d` を代入した文の語数（句読点を除く）

#### P05 — Practice (10問, Q16–Q25)

| 問番号 | 語数範囲   | 問番号 | 語数範囲   |
|---|------|---|------|
| Q16 | 15–17語 | Q21 | 21–23語 |
| Q17 | 18–20語 | Q22 | 18–20語 |
| Q18 | 21–23語 | Q23 | 15–17語 |
| Q19 | 18–20語 | Q24 | 18–20語 |
| Q20 | 15–17語 | Q25 | 15–17語 |

正解分布: 各文字 **max 4 個**

#### FM05 — Full Mock (25問, Q16–Q40)

語数: Short(15–17) / Medium(18–20) / Long(21–23) をシャッフル配置

正解分布: 各文字 **max 7 個**（target \~6–7 of each）

#### SM05 — Short Mock (8問, Q16–Q23)

| 問番号 | 語数範囲   |
|---|------|
| Q16 | 15–17語 |
| Q17 | 18–20語 |
| Q18 | 21–23語 |
| Q19 | 18–20語 |
| Q20 | 15–17語 |
| Q21 | 21–23語 |
| Q22 | 18–20語 |
| Q23 | 15–17語 |

正解分布: 各文字 **max 3 個**

---

## Reading

### パッセージブロック構造

```
===PASSAGE===

@passage
<本文テキスト。段落は空行（\n\n）で区切る>

@passage_theme
分野：テーマ名

===END_PASSAGE===
```

- `@passage_theme` の形式: `分野：テーマ名`

  - 例: `生物学：光合成のメカニズム`, `歴史：産業革命と社会変革`

  - 前半はアカデミック分野、後半はそのパッセージ固有のテーマ名

- `===END_PASSAGE===` はなくても動作するが、あれば優先される

### Vocabulary / Usage マーカー

**FastAPI はマーカーを自動注入しない。生成時に必ず埋め込む。**

```
@passage 内:
"The [U1]swift[/U1] river carries sediment downstream."

@question_text 内:
"The word "[U1]swift[/U1]" in paragraph 1, sentence 3 is closest in meaning to ..."
```

- `[U{n}]...[/U{n}]` を `@passage` と `@question_text` 両方に記述

- n は **そのパッセージ内で Vocabulary と Usage が共有するカウンター**（1始まり）

- パッセージ内の左→右の出現順に n=1, 2, 3, ... を割り当てる

- **n はパッセージごとにリセット**

- `<< >>` 記法は Reading では使用しない

### 問題フィールド一覧（P06 / FM06 / SM06 共通）

```
===ITEM:N===

@question_text
<質問文。Vocab/Usage は [U{n}] マーカー込みで記述>

@target_phrase
<Vocab/Usage のみ: マーカーなしの対象語（例: swift）。他は null>

@target_paragraph
<Vocab/Usage のみ: 段落番号（1始まり）。他は null>

@target_sentence
<Vocab/Usage のみ: 段落内文番号（1始まり）。他は null>

@choice_a
@choice_b
@choice_c
@choice_d
@correct_choice
<A|B|C|D>

@tag
<mainIdea|fact|inference|vocab|usage|not|rhetorical|organization|location|viewpointTone>

@explanation
<日本語>

@wrong_reason_a
<日本語 or null>
@wrong_reason_b
<日本語 or null>
@wrong_reason_c
<日本語 or null>
@wrong_reason_d
<日本語 or null>

===END:N===
```

### 1パッセージあたりの問題構成（固定）

| 問題タイプ          | @tag          | P06 | FM06 / SM06 | 位置ルール            |
|--------------|-------------|---|-----------|----------------|
| Main Idea      | mainIdea      | 1   | 1           | 必ず第 1 問          |
| Factual        | fact          | 2   | 2           | —                |
| Inference      | inference     | 2   | 2           | 最終問は必ず inference |
| Vocabulary     | vocab         | 2   | 3           | —                |
| Usage          | usage         | 1   | 1           | —                |
| NOT            | not           | 1   | 1           | —                |
| Rhetorical     | rhetorical    | 1   | 1           | —                |
| Organization   | organization  | 0   | 0           | —                |
| Location       | location      | 0   | 0           | —                |
| Viewpoint/Tone | viewpointTone | 0   | 0           | —                |
| 合計             | —             | 10  | 10          | —                |

問題順序ルール:

- Q1（各パッセージ先頭）は必ず **Main Idea**

- 最終問（各パッセージ末尾）は必ず **Inference**

- Q2 〜 最終問の 1 つ前は、パッセージ内の情報出現順に沿って配置する（答えのヒントが前の問題より前に現れてはいけない）

---

### P06 — Practice Reading（Long × 1パッセージ、10問）

| 項目            | 値          |
|-------------|----------|
| パッセージ数        | 1（Long のみ） |
| 問題数           | 10         |
| アイテム番号        | 1–10       |
| vocab 数/パッセージ | 2          |

**出力構造**:

```
===PASSAGE===
@passage
...
@passage_theme
...
===END_PASSAGE===

===ITEM:1===
...
===END:1===

(===ITEM:2=== 〜 ===ITEM:10=== を繰り返す)
```

---

### FM06 — Full Mock Reading（5パッセージ × 10問 = 50問）

| 項目            | 値                                                         |
|-------------|---------------------------------------------------------|
| パッセージ数        | 5（Long, Short, Long, Short, Long）                         |
| 問題数           | 50                                                        |
| アイテム番号        | グローバル連番 1–50                                              |
| パッセージ割り当て     | P1: Q1–10, P2: Q11–20, P3: Q21–30, P4: Q31–40, P5: Q41–50 |
| vocab 数/パッセージ | 3                                                         |
| [Un] カウンター    | パッセージごとにリセット                                              |

**固定位置**:

- Q1, Q11, Q21, Q31, Q41 → `mainIdea`

- Q10, Q20, Q30, Q40, Q50 → `inference`

**出力構造**:

```
===PASSAGE===   ← passage 1 (Long)
@passage / @passage_theme
===END_PASSAGE===
===ITEM:1=== ... ===END:1===
...
===ITEM:10=== ... ===END:10===

===PASSAGE===   ← passage 2 (Short)
...
===END_PASSAGE===
===ITEM:11=== ... ===END:11===
...
===ITEM:20=== ... ===END:20===

(passage 3–5 も同様)
```

---

### SM06 — Short Mock Reading（2パッセージ × 10問 = 20問）

| 項目            | 値                     |
|-------------|---------------------|
| パッセージ数        | 2（Long, Short）        |
| 問題数           | 20                    |
| アイテム番号        | グローバル連番 1–20          |
| パッセージ割り当て     | P1: Q1–10, P2: Q11–20 |
| vocab 数/パッセージ | 3                     |
| [Un] カウンター    | パッセージごとにリセット          |

**固定位置**:

- Q1, Q11 → `mainIdea`

- Q10, Q20 → `inference`

**出力構造**:

```
===PASSAGE===   ← passage 1 (Long)
...
===END_PASSAGE===
===ITEM:1=== ... ===END:10===

===PASSAGE===   ← passage 2 (Short)
...
===END_PASSAGE===
===ITEM:11=== ... ===END:20===
```

---

## セクション別サマリー

| セクション | ファイル                      | モード        | 種別          | 問題数         | 主な特徴                                  |
|-----|-------------------------|----------|-----------|-----------|-------------------------------------|
| P01   | P01_Listening_Part_A.txt  | Practice   | Listening A | 12          | shortConv                             |
| P02   | P02_Listening_Part_B.txt  | Practice   | Listening B | 8           | longConv, 2スクリプト×4問                   |
| P03   | P03_Listening_Part_C.txt  | Practice   | Listening C | 8           | talk, 2スクリプト×4問                       |
| P04   | P04_Grammar_Part_A.txt    | Practice   | Grammar A   | 10          | underline_target必須, 語数 tier 3段階       |
| P05   | P05_Grammar_Part_B.txt    | Practice   | Grammar B   | 10 (Q16-25) | question_template+chunk, choice="A"等  |
| P06   | P06_Reading_Long.txt      | Practice   | Reading     | 10          | Long×1, vocab×2, [Un] marker          |
| FM01  | FM01_Listening_Part_A.txt | Full Mock  | Listening A | 30          | shortConv                             |
| FM02  | FM02_Listening_Part_B.txt | Full Mock  | Listening B | 8           | longConv, 2スクリプト×4問                   |
| FM03  | FM03_Listening_Part_C.txt | Full Mock  | Listening C | 12          | talk, 3スクリプト×4問                       |
| FM04  | FM04_Grammar_Part_A.txt   | Full Mock  | Grammar A   | 15          | underline_target必須, 語数 tier 3段階       |
| FM05  | FM05_Grammar_Part_B.txt   | Full Mock  | Grammar B   | 25 (Q16-40) | max 7 of any letter                   |
| FM06  | FM06_Reading.txt          | Full Mock  | Reading     | 50          | 5パッセージ(L/S/L/S/L), vocab×3            |
| SM01  | SM01_Listening_Part_A.txt | Short Mock | Listening A | 8           | shortConv                             |
| SM02  | SM02_Listening_Part_B.txt | Short Mock | Listening B | 8           | longConv, 2スクリプト×4問                   |
| SM03  | SM03_Listening_Part_C.txt | Short Mock | Listening C | 8           | talk, 2スクリプト×4問                       |
| SM04  | SM04_Grammar_Part_A.txt   | Short Mock | Grammar A   | 8           | underline_target必須, max ~2 per letter |
| SM05  | SM05_Grammar_Part_B.txt   | Short Mock | Grammar B   | 8 (Q16-23)  | max 3 of any letter                   |
| SM06  | SM06_Reading.txt          | Short Mock | Reading     | 20          | 2パッセージ(Long+Short), vocab×3           |
