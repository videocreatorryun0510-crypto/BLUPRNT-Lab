# ADR-0009: Provider-neutral Presentation Engine Adapter

- Status: Accepted
- Date: 2026-08-03

## Context

Presentation RequestをGeminiへ直接変換すると、認証、Payload、実行、応答検証、監査がGemini固有実装へ結合します。将来ClaudeやOpenAIへ交換する際、WorkbenchやApproval Gateまで変更される危険があります。

## Decision

Provider固有実装の手前に、Version付きのPresentation Engine Adapter InterfaceとPresentation Result Contractを置きます。

- RunnerがRegistry整合性、既存Approval Gate、監査を担当する
- AdapterがRequest検証、Payload構築、実行、応答正規化・検証を担当する
- Resultは本文を持たず、実行と検証のメタデータだけを持つ
- Phase 5.16ではネットワーク通信を持たないDummy Adapterだけを実装する
- PreviewでもGateを評価するが、Externalだけが承認許可を必須とする

## Consequences

- Gemini、Claude、OpenAIを同じContractへ追加できる
- Providerの変更がKnowledge Platformへ波及しない
- Dummyだけで承認・Fingerprint・件数・監査の全フローを検証できる
- Provider固有機能は共通Contractの外に隔離される

将来の実AI接続では、承認済み医学本文を安全に解決してProviderへ渡す境界と、生成本文のClaim単位検証が別途必要です。

## Rejected alternatives

### Gemini専用Publisher

Provider交換時にPresentation Request、Workbench、監査が影響を受けるため採用しません。

### Provider SDKをRunnerへ直接配置

承認・監査と通信技術の責務が混ざるため採用しません。

### ResultへAI生成本文を保存

医学レビュー前の文章が正本のように扱われる危険があるため、MVPでは採用しません。
