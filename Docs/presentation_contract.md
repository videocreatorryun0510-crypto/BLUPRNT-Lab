# Presentation Contract MVP

## 1. 役割

Presentation Contract Version 1.0は、Source Bundleから成果物を作る際の
「誰向けに、どの形式で、どの安全条件を守るか」を表すAI非依存の契約です。

```text
Knowledge Registry（医学的事実の正本）
        ↓
Source Bundle（教育データの正本）
        ↓
Approval Gate
        ↓
Presentation Request（成果物の生成条件）
        ↓（次Phase以降）
Gemini / Claude / OpenAI / Canva / NotebookLM
```

Presentation RequestはClaim本文やSource Bundle全文を複製しません。安定IDと
Fingerprintで参照するため、医学的事実の正本はRegistry、教育データの正本はSource
Bundleのままです。

## 2. Contract

| ブロック | 主な内容 |
|---|---|
| `identity` | Request ID、Contract Version、生成日時 |
| `source` | Knowledge ID・Version、Source Bundle Version、Fingerprint、承認状態、Review Version |
| `presentation` | Presentation Type、題名、対象者、学習目的、言語、Output Format |
| `content_policy` | 使用Claim、Key Message、Diagram Request、Reference、医学的変更の禁止 |
| `layout_policy` | ページ／スライド数、比率、向き、情報密度、図優先度、文字量 |
| `validation_policy` | Claim・Reference追跡、未承認追加禁止、Fingerprint・Approval Gate必須 |
| `metadata` | BuilderとPresentation ProfileのID・Version |

`allow_non_medical_presentation_text`だけを`true`とし、見出し、章タイトル、意味を
変えない短いラベルを将来許可できる余地を残します。医学的な言い換えと事実追加は
`false`です。

## 3. Presentation TypeとOutput Format

Typeは用途、Formatはファイル形式として分離します。

列挙済みType：

- `presentation_document`
- `pdf_material`
- `instagram_slides`
- `training_material`
- `diagram`
- `notebook_material`

列挙済みFormat：

- `structured_json`
- `pdf`
- `pptx`
- `png_sequence`
- `html`
- `markdown`

MVPで生成できる組み合わせは`presentation_document`と`structured_json`だけです。

## 4. Profile

`presentation_document_basic_v1` Version `1.0`を用意しました。

- 対象者：臨床検査技師国家試験を学習する学生
- 5ページ／スライド
- 16:9・横向き
- 情報密度：low
- 図解優先：high
- 文字量：short
- 出典・国家試験ポイント：含める
- 医学的言い換え・事実追加：禁止

フェリチンや鉄欠乏性貧血の医学情報はProfileへ保存しません。同じProfileを両方へ
適用します。

## 5. PreviewとExternal

| Mode | draft | owner_review | medical_review | approved | published | deprecated |
|---|---:|---:|---:|---:|---:|---:|
| Preview | 可 | 可 | 可 | 可 | 停止 | 停止 |
| External | 停止 | 停止 | 停止 | 可 | 停止 | 停止 |

Externalは既存の`can_send_to_external_ai()`を必ず通ります。今回は外部APIを呼びません。

## 6. Stale Source防止

Request生成前に次をRegistry最新版と比較します。

- Knowledge Version
- Source Fingerprint
- Approval State
- Review Version

不一致時はRequestを保存せず、`source_bundle_stale`と具体的な理由を返します。

- `knowledge_version_mismatch`
- `fingerprint_mismatch`
- `approval_state_changed`
- `review_version_mismatch`

## 7. Traceability

Presentation Requestは次だけを参照します。

- `selected_claim_ids`
- `key_message_claim_ids`
- `diagram_request_ids`
- `reference_ids`
- `source_fingerprint`

Builderは医学的文章を生成・変更しません。

## 8. 保存と監査

生成物：

```text
Publisher Output/presentation_request/
└── knw_10000013_v1.preview.presentation-request.json
```

監査ログ：

```text
Publisher Output/logs/presentation_request.jsonl
```

どちらも派生データでありGitへ保存しません。Requestは一時ファイルからの安全な置換で
保存します。監査ログには判定条件と結果だけを記録し、Source Bundle全文やClaim本文を
保存しません。

## 9. 今回の対象外

- Gemini、Claude、OpenAI等への送信
- Provider固有Prompt
- PDF、PowerPoint、画像、動画の生成
- Profile編集UI
- AI生成結果の保存・医学レビュー・公開
