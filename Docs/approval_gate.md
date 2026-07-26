# Approval Gate MVP

## 1. 目的

Approval Gateは、医学監修が完了していないKnowledgeが外部AIや公開処理へ進むことを
防ぐ共通の安全装置です。Gemini、Claude、GPT、PDF等の個別技術には依存しません。

Source Bundleの生成はレビュー作業なので`draft`でも許可します。外部へ出す操作だけを
Gateで止めます。

```text
Knowledge Registry
        ↓
Approval Snapshot
        ├─→ Source Bundle生成（draftでも可）
        ↓
Approval Gate
        ├─ can_publish()
        └─ can_send_to_external_ai()
                 ↓ approvedだけ許可
          将来のPresentation Engine
```

## 2. Approval Contract Version 1.0

正式な承認順は次のとおりです。

```text
draft
  ↓
owner_review
  ↓
medical_review
  ↓
approved
  ↓
published（将来利用）
```

差し戻しは隣の承認段階へ戻せます。状態変更のたびに日時、操作者、コメントをRegistryへ
保存します。`deprecated`は承認段階ではなく、既存Registryとの互換性を保つ廃止状態です。

## 3. Approval Snapshot

Registryから次の情報だけを読み取り、WorkbenchとSource Bundleで共通利用します。

| 項目 | 意味 |
|---|---|
| `approval_state` | 現在の承認状態 |
| `approved_at` | 最後に`approved`となった日時 |
| `approved_by` | 最後の承認者 |
| `review_version` | 判定対象のKnowledge Version |
| `review_required` | 再確認が必要か |

Knowledge JSON本文へ承認情報は追加しません。承認の正本はRegistryです。

## 4. Gate仕様

| 判定 | `approved` | それ以外 |
|---|---:|---:|
| `can_publish()` | `true` | `false`と理由 |
| `can_send_to_external_ai()` | `true` | `false`と理由 |

Version 1.0では`published`も再送信を許可しません。公開済み成果物の再送信・再公開ルールは、
成果物版と権限管理を設計する将来Phaseで定義します。

## 5. Publisher監査ログ

既定の保存先：

```text
Publisher Output/
└── logs/
    └── approval_gate.jsonl
```

1行が1回の判定です。Knowledge ID、判定対象、Approval State、結果、理由、Review Version、
Timestampを記録します。Source BundleやKnowledge本文は監査ログへ複製しません。

## 6. Workbench確認

1. フェリチンまたは鉄欠乏性貧血を開く
2. Knowledge編集欄の`Approval State`を確認する
3. `Source Bundle生成`を押す
4. `公開可否`と`外部AI送信`を確認する
5. 下書きでは両方が`停止`になり、理由と監査ログ保存先が表示される

既存のRegistry承認操作は維持していますが、Phase 5.14で新しいReviewer画面や権限管理は
追加していません。

## 7. 安全境界

- Knowledge JSON、Claim本文、Relationは変更しない
- Source Bundle生成と外部送信許可を分離する
- 外部AI Adapterは将来必ずGate結果を確認してから送信する
- Providerごとに承認ルールを複製しない
- Gateの許可条件をUI表示だけに依存させない

## 8. 対象外

- Gemini API接続
- Medical Review専用UI
- Reviewer権限・電子署名
- Source Bundle成果物自体の承認と世代管理
- 公開済み成果物の取消し・再公開
