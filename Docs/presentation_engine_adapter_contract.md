# Presentation Engine Adapter Contract MVP

## 1. 役割

Presentation Engine Adapter Contract Version 1.0は、Presentation RequestをどのPresentation Engineでも同じ手順で検証・実行・監査するための境界です。

```text
Knowledge Registry
        ↓
Source Bundle
        ↓
Presentation Request
        ↓
Presentation Engine Runner
        ├── Approval Gate
        ├── Request Validation
        └── Audit
        ↓
Presentation Engine Adapter Interface
        ├── Dummy（Phase 5.16）
        ├── Gemini（将来）
        ├── Claude（将来）
        └── OpenAI（将来）
        ↓
Presentation Result
```

既存のKnowledge、Registry、Claim、Relation、Source Bundle、Approval Gate、Presentation Request、Publisher Coreは変更しません。

## 2. Adapter Interface

すべてのProvider Adapterは次の同じ契約を実装します。

- `provider_name`
- `provider_version`
- `supports_preview`
- `supports_external`
- `validate_request()`
- `build_payload()`
- `execute()`
- `validate_response()`

Provider固有のSDK、認証、API URL、Prompt、応答形式は将来の個別Adapter内部だけに置きます。

## 3. Dummy Adapter

Dummy Adapter Version `1.0.0`はPreviewとExternalの両方を模擬できます。Externalは承認済みRequestだけが対象です。

`execute()`はネットワーク通信をせず、次のメタデータだけを返します。

- status
- provider / provider_version
- pages
- claims_used
- diagram_requests
- references
- output_type
- request_fingerprint

APIキー、Provider SDK、医学本文、Source Bundle本文は使用しません。

## 4. Presentation Result Contract

Presentation Result Version 1.0は次を保持します。

- request_id
- provider / provider_version
- status
- created_at
- validation_result
- generated_artifacts
- warnings
- errors

`generated_artifacts`は成果物ID、種別、ページ数、使用件数、Request Fingerprintだけを持ちます。医学本文や完成原稿は保存しません。

## 5. Validation

### Request Validation

- AdapterがRequest Modeへ対応している
- 医学的な言い換えが禁止されている
- 医学的事実の追加が禁止されている
- Claim・Reference追跡が必須である
- Fingerprint・Approval Gateが必須である
- Knowledge ID・Version・Approval State・Review VersionがRegistry最新版と一致する

### Response Validation

- Request ID
- Request Fingerprint
- Provider / Provider Version
- Claim数
- Diagram Request数
- Reference数
- ページ数
- Output Type
- 成功状態とErrorの有無

不一致時は`failed`とし、`generated_artifacts`を利用可能なResultへ載せません。

## 6. Approval Gate

RunnerはPreview・Externalの両方で既存`can_send_to_external_ai()`を呼び、判定を監査します。

| Mode | Gateの扱い | Dummy実行 |
|---|---|---|
| Preview | 判定・記録するが外部送信許可は要求しない | レビュー途中でも可 |
| External | `approved`の許可を必須とする | 許可時だけ可 |

Previewはローカル検証であり、外部AIへ送信しません。

## 7. Payloadと医学的安全性

MVPの共通Payloadは次だけを持ちます。

- Request ID・Fingerprint・Mode
- Provider・Version
- Presentation Type・Output Format・予定ページ数
- Claim ID・Diagram Request ID・Reference ID

医学本文をAdapterへ渡さないため、Dummy Adapterが内容を書き換えることはできません。将来、Providerへ本文を渡す必要が生じた場合は、承認済みSource Bundleを読み取る別の安全な解決境界を設計します。

## 8. Audit

保存先：

```text
Publisher Output/logs/presentation_engine.jsonl
```

記録内容：

- request_id
- provider / provider_version
- mode
- status
- validation_result
- gate_result
- timestamp

Presentation Request全文、Source Bundle全文、Claim本文、AI応答本文は保存しません。

## 9. Workbench

Source BundleとPresentation Requestを生成後、「Dummy Adapter実行」を押すと次を表示します。

- Preview / External
- AdapterとVersion
- Validation
- Result
- Pages / Claims / Diagrams / References
- Request Fingerprint
- Approval Gate確認
- 監査ログ保存先
- Result JSON全文

## 10. 対象外

- Gemini・Claude・OpenAI API
- Provider固有Prompt
- PDF・PowerPoint・画像・動画生成
- AI応答本文の保存・医学レビュー・公開
- AdapterによるKnowledge変更
