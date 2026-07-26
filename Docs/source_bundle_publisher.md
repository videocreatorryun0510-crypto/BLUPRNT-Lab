# Source Bundle Publisher MVP

## 1. 役割

Source Bundle Publisherは、BLUPRNT Labの正本データを、GeminiなどのPresentation
Engineが読みやすいJSONへ変換する読取専用コンポーネントです。

```text
Knowledge JSON ─┐
Registry ───────┼─→ Source Bundle Publisher ─→ Source Bundle JSON
Exam Metadata ──┘                                  ↓（将来）
                                             Presentation Engine
                                      PDF / Slide / Instagram / Video
```

Knowledge、Registry、Exam Metadataは書き換えません。PDF、PowerPoint、画像、動画、
Gemini向けPromptも生成しません。

## 2. Version 1.0契約

| 項目 | 内容 | 情報源 |
|---|---|---|
| `title` | 正式名称 | Knowledge |
| `summary` | Profileが指定した既存Claim本文 | Knowledge / Registry |
| `learning_objective` | 教材の学習目的 | Source Bundle Profile |
| `target_audience` | 対象学習者 | Source Bundle Profile |
| `claims` | 有効ClaimのID、Key、保存場所、本文 | Registry |
| `key_messages` | Profileで選んだ重要Claim | Registry |
| `exam_points` | Exam Metadataの重要Claim。未登録時は空配列 | Exam Metadata |
| `diagram_requests` | 図の題名、目的、根拠Claim ID | Source Bundle Profile |
| `references` | Knowledgeの出典情報 | Knowledge |
| `metadata` | Knowledge ID、版、Category、状態、承認者・日時、Review Version、再確認要否、Publisher版、生成日時、Fingerprint | 各正本 |

`claims`と`key_messages`の`assertion`は既存Claim本文をそのまま使用します。Publisherは
医学的な文章を作りません。

## 3. MVP対象

| Knowledge | knowledge_id | Claim数 | 図解要求 |
|---|---|---:|---|
| フェリチン | `knw_10000013` | 11 | 鉄代謝の概略図 |
| 鉄欠乏性貧血 | `knw_10000012` | 17 | 鉄欠乏による赤血球形成低下 |

両KnowledgeはExam Metadataが未登録のため、`exam_points`は空配列です。

## 4. 保存

既定の保存先：

```text
Publisher Output/
└── source_bundle/
    ├── knw_10000012_v1.source-bundle.json
    └── knw_10000013_v1.source-bundle.json
```

同じKnowledge Versionを再生成した場合は同名ファイルを安全に置換します。Knowledgeの版が
上がるとファイル名の`v1`も変わります。保存先は`SOURCE_BUNDLE_OUTPUT_DIR`で変更できます。

## 5. Workbench操作

1. 「鉄欠乏性貧血を開く」または「フェリチンを開く」を押す
2. 保存済みの正本であることを確認する
3. 「Source Bundle生成」を押す
4. 保存先、Knowledge Version、承認状態を確認する
5. 公開可否・外部AI送信可否と理由を確認する
6. 画面に表示されたJSON全文を確認またはコピーする

生成対象は編集中の未保存JSONではなく、Registryへ最後に保存した版です。

## 6. 安全境界

- Source Bundle生成はKnowledge本文・Registry・Relationを更新しない
- 対応ProfileがないKnowledgeは推測で生成しない
- Exam Metadataが空なら`exam_points`も空にし、AIで補完しない
- Diagram RequestはClaim IDを根拠として保持し、画像やPromptを保存しない
- `metadata.status`へ`draft`・`approved`などを明示する
- `metadata.approval_state`、`approved_at`、`approved_by`、`review_version`、
  `review_required`を保持する
- `draft`生成はWorkbench内レビュー用であり、外部送信・公開許可ではない
- `can_publish()`と`can_send_to_external_ai()`は`approved`だけを許可する
- Gate判定は`Publisher Output/logs/approval_gate.jsonl`へ追記する

## 7. 今回の対象外

- Gemini API接続
- Gemini固有Prompt
- PDF、PowerPoint、Canva、Markdown、HTML、動画生成
- Source Bundle成果物自体の承認・世代保管
- Source Bundle ProfileのWorkbench編集
- 12年分CSV由来Exam Metadataの正式永続保存
