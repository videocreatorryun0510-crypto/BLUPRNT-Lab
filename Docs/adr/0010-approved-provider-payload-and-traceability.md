# ADR-0010: Approved Provider Payload and Response Traceability

- Status: Accepted
- Date: 2026-08-03

## Context

Presentation Requestは参照IDと生成条件だけを持つため、外部AIは医学内容を理解できません。一方、各Provider AdapterがRegistryやSource Bundleを直接読む設計では、承認・Stale確認・送信範囲・Secret検査がProviderごとにばらつきます。

## Decision

Provider Adapterの前段に、独立したProvider Payload ResolverとProvider共通Data Egress Policyを置きます。

- ResolverだけがPresentation RequestのIDを承認済み正本へ解決する
- Claim本文はRegistry最新版を一字も変えずに複写する
- Previewを含め、未承認Claimを含むProvider Payloadは生成しない
- ProviderはRegistry、Source Bundle、Knowledge本文へ直接アクセスしない
- PayloadとResponseへIDベースのTraceability Mapを持たせる
- Payload Fingerprintで正本、Request、Policyの組合せを固定する
- 既存Adapter Interfaceは変更せず、Traceable Payload実行を追加Capabilityとする

## Consequences

- Gemini、Claude、OpenAI、Canva、NotebookLMで同じ承認済みPayloadを利用できる
- Provider追加でKnowledge Platformの安全Policyを再実装する必要がない
- AI応答がどのClaim・出典・図解要求を使ったか検証できる
- draftのWorkbenchでは停止理由の確認までとなり、Payload全文の確認には承認済みFixtureまたは正式承認が必要になる

## Rejected alternatives

### Provider AdapterがRegistryを直接読む

Providerごとに承認、Stale、Secret、最小送信の実装が分岐するため採用しません。

### draft ClaimをPreview Payloadへ含める

Previewから誤って外部送信される経路を作るため、安全側の初期Policyでは採用しません。

### Gemini専用Promptへ医学本文を展開する

Provider交換が困難になり、Claim単位の追跡も失われるため採用しません。

### AI応答本文をResponse Contractへ保存する

未監修文章を正本と誤認する危険があるため、MVPではMetadataとTraceabilityだけを保存します。
