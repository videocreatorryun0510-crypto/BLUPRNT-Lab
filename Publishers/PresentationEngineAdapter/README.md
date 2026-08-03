# Presentation Engine Adapter Contract — Phase 5.16 / 5.17

Presentation Requestと外部Presentation Engineの間に置く、Provider非依存の境界です。

```text
Presentation Request
        ↓
Presentation Engine Runner（Approval Gate・監査）
        ↓
Presentation Engine Adapter Interface
        ├── Dummy Adapter（実装済み・通信なし）
        ├── Gemini Adapter（将来）
        ├── Claude Adapter（将来）
        └── OpenAI Adapter（将来）
```

## MVPの責務

- 共通Adapter Interfaceを固定する
- Presentation Requestを検証する
- Requestの正規化Fingerprintを計算する
- PreviewでもApproval Gate判定を記録する
- Externalは既存Approval Gateが許可した場合だけ実行する
- Dummy応答のFingerprint・Claim数・図解数・出典数・Provider Versionを検証する
- 本文や医学知識をResult・Auditへ保存しない

Dummy AdapterはネットワークライブラリやAPIキーを使用しません。`execute()`は件数と成果物種別だけを持つメタデータ応答を返します。

Phase 5.17では`execute_traceable_payload()`を追加しました。承認済み正本からProvider Payload Resolverが生成した`PresentationPayload`を受け取り、医学本文をResultへ複製しないTraceable Responseを返します。

Phase 5.16の`PresentationRequest -> build_payload() -> execute()`経路は互換性維持のため残していますが、実Provider追加時はPhase 5.17のTraceable Payload経路を利用します。既存の`PresentationEngineAdapter` Interfaceそのものは変更していません。

## Presentation Result Version 1.0

ResultはRequest ID、Provider、状態、検証結果、生成物メタデータ、Warning、Errorだけを持ちます。`generated_artifacts`にも本文、Claim本文、Source Bundleは含めません。

## Approval Gate

- Preview：既存Gateを評価・監査するが、外部送信ではないためレビュー途中でもDummy実行可能
- External：`approved`かつ既存`can_send_to_external_ai()`が許可した場合だけ実行可能

## 対象外

- Gemini・Claude・OpenAI API
- Provider固有Prompt
- PDF・PowerPoint・画像・動画生成
- AI応答本文の保存
- 医学知識の生成・変更
