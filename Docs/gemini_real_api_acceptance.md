# Phase 5.18.1 Gemini Sandbox Real API Acceptance

## 目的

GeminiをPresentation Engineとして安全に接続できることを、実Knowledgeとは分離した承認済みTest Fixtureで1回だけ確認する。

```text
Approved Test Fixture（隔離SQLite）
  → Source Bundle
  → Presentation Request
  → Provider Payload
  → Provider-neutral Presentation Prompt
  → Gemini Sandbox Adapter
  → Gemini Interactions API
  → Response Mapper
  → Traceable Response
  → 本文なしAudit
```

## 安全境界

- 実RegistryのKnowledge、Claim、承認状態、履歴、Relationは読み取り確認だけとし、変更しない。
- Test Fixtureは一時SQLite内だけで`approved`へ進める。
- 外部送信はWorkbenchの専用ボタンによる明示操作1回だけとする。
- ページ読込、Knowledge保存、送信前確認では外部通信しない。
- Fixtureは2 Claim、1 Reference、0 Diagram Request、3ページ以下とする。
- APIキーは`.env`だけから読み、画面・レスポンス・監査へ値を出さない。
- `store=false`を指定し、APIキー、Header、Prompt全文、Provider生Response、医学本文を保存しない。

## 送信前確認

WorkbenchはProvider、Sandbox Mode、Model、Fixture ID、Approval、件数、Payload Fingerprint、Data Egress Policy、Secret Scan、Stale Check、送信文字数、最大出力Token、Retry、Timeout、外部通信の有無を表示する。APIキーは値ではなく「設定済み／未設定」だけを表示する。

## Response Acceptance

Geminiには短い構造化JSONのみを要求する。

- `title`
- `sections`
- `source_claim_ids`
- `source_reference_ids`
- `warnings`

受信後はProvider Request ID、JSON形式、Payload Fingerprint、Claim ID、Reference ID、必須項目、無変更Claim本文を検証する。通信成功と受入成功を分離し、不一致は`validation_failed`として採用を停止する。

## 保存する監査情報

監査ログはExecution、Request、Payload、ResponseのID、Provider、Model、Sandbox／Fixture識別、開始・完了時刻、所要時間、Token、Retry、通信結果、検証結果、最終結果、Error Codeだけを保存する。

## 実行制約

- 正常系の明示実行はWorkbench起動ごとに1回。
- 一時エラーのRetryは最大1回。
- 実APIで意図的なエラーを発生させない。
- 認証、Timeout、429、500、不正JSON、Fingerprint、Claim、Referenceの異常系はMockで確認する。

## 運用手順

1. `Prototypes/KnowledgeWorkbench/.env`へユーザー自身が`GEMINI_API_KEY`を入力する。
2. Workbenchを再起動する。
3. 「送信前確認を作成」を押す。この操作は外部通信しない。
4. 全項目とPayload Fingerprintを確認する。
5. 「Test FixtureをGeminiへ1回送信」を1回だけ押す。
6. Transport、Validation、Claim／Reference、Token、Duration、Registry不変、Audit保存を確認する。

実Knowledgeを使用したGemini受入は、医学レビュー、操作者権限、承認条件を確定した別Phaseで行う。

