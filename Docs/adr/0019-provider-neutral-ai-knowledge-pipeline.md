# ADR 0019: AI Knowledge生成をProvider非依存PipelineからAuthoring Draftへ限定する

- Status: Accepted
- Date: 2026-08-11
- Phase: 5.24 AI Knowledge Pipeline MVP

## Context

Phase 5.22のAuthoring Workflowは、人がClaimとReferenceを1件ずつ入力する安全な経路を確立した。しかし1000件以上のKnowledgeを作成するには入力工数が大きい。AI生成へ移行する一方で、検索Provider、LLM、Workbench、Promotion、Review、Registryを直接結合すると、AI会社の変更や未確認情報の正式登録が困難になる。

## Decision

1. ThemeからAuthoring Draftまでを独立した`KnowledgePipelineService`で統括する。
2. Evidence Search Provider、Evidence Ranker、Claim BuilderをProtocolとして交換可能にする。
3. Provider応答はEvidence Search Contract 1.0へ正規化してから後段へ渡す。
4. Claim候補は必ず根拠Evidence IDを持ち、Reference Builderが既存Authoring Referenceへ変換する。
5. Knowledge Builderは既存Knowledge Contractに適合するSkeletonを再利用し、Contractを変更しない。
6. PreviewとAuthoring Draft保存を分け、Previewだけでは永続化しない。
7. Pipelineの保存先をAuthoring Draftに限定し、Promotion、Review、Approval、Registryを自動実行しない。
8. MVPでは実検索・LLMを接続せず、既存ローカルKnowledge例の本文を変えないFixtureで境界を検証する。
9. 対応Fixtureがない用語は推測せず停止する。

## Not selected

- WorkbenchからOpenAIへ直接問い合わせる案：Provider固有処理が画面へ混入する。
- Search結果からRegistryへ直接登録する案：Preview、修正、Review、Approvalを迂回する。
- LLMにEvidence・Claim・Reference・Knowledge JSONを一度に生成させる案：責務と失敗原因を分離できず、根拠追跡が弱くなる。
- MVPのために擬似医学情報を生成する案：未検索・未生成である事実を隠し、誤認につながる。
- Promotionを同時実行する案：Phase 5.23の人による明示確定境界を壊す。

## Consequences

実Provider接続前のため、Sandboxで生成できるのはフェリチン、鉄欠乏性貧血、Gram染色の3テーマだけである。一方、外部APIなしで全経路、追跡性、Preview、保存境界を再現できる。

実検索Provider追加時には、Evidenceの重複排除、引用範囲、利用規約、失効、Rate Limit、キャッシュ、Cost、検索監査を追加する必要がある。LLM Claim Builder追加時にはPrompt Contract、構造化出力、幻覚検知、Claim粒度、Confidenceの意味を正式化する必要がある。

## Compatibility

Knowledge Contract、Claim、Registry、Relation、Approval Gate、Source Bundle、Presentation、Artifact、Publisher Coreに変更はない。既存Authoring Serviceには、Preview用の非保存Skeleton生成と、検証済み生成Draft保存の入口だけを追加した。
