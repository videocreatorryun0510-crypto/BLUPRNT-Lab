# ADR 0020: Raw Evidenceを内部限定しEvidence Bundleを唯一の後段契約とする

- Status: Accepted
- Date: 2026-08-11
- Phase: 5.25 Evidence Intelligence Layer MVP

## Context

Phase 5.24では検索、Claim、Reference、KnowledgeをProvider非依存の処理へ分けた。しかし検索Providerの応答を直接WorkbenchやClaim Builderへ渡すと、Provider変更のたびに画面と後段処理が変わり、同じ根拠の重複、根拠レベル、取得元を一貫して扱えない。

## Decision

1. Provider応答を`RawEvidenceSearchResult`としてNormalizer内部までに限定する。
2. ProviderごとのNormalizerが共通Evidence Contract 1.0へ変換する。
3. DOI、PMID、URL、資料名類似度による重複排除を独立コンポーネントで行う。
4. Evidence Level A、B、Cを第一基準として順位付けする。
5. Information Priorityは同Level内の補助基準とし、Evidence Levelと統合した不透明な点数を作らない。
6. Claim BuilderとWorkbenchはEvidence Bundle 1.0だけを受け取る。
7. Search Auditには検索条件、Provider、件数、採用・除外ID、時刻、所要時間だけを保存し、医学本文を保存しない。
8. Knowledge Contract、Promotion、Registry、Approval、Artifact、Renderer、Prompt Builderは変更しない。

## Not selected

- Provider応答をWorkbenchへ直接表示する案：Provider変更がUI変更になり、固有情報が漏れる。
- Claim Builderごとに標準化する案：重複処理が増え、同じEvidenceを違う形で扱う。
- すべてを1つの総合Scoreへ変換する案：Evidence Levelと情報取得優先順位の意味が失われる。
- タイトル一致だけで重複排除する案：別資料の誤統合リスクが高い。
- Search AuditへSnippetを保存する案：医学本文の不要な複製になる。

## Consequences

新Providerは独自応答を保持したまま追加できるが、必ずNormalizerを実装する必要がある。DOI・PMID・URLがない資料のタイトル類似判定には限界があり、人の確認が必要である。MVPではローカルFixtureだけを使用し、実Providerの認証、Rate Limit、利用規約、失効監視、キャッシュは未実装である。

## Compatibility

Phase 5.24の内部Evidence経路をVersion 1.1へ更新するが、生成されるAuthoring Draftと既存Knowledge Contractは変わらない。Registry、Promotion、Approval、Presentation、Artifact、Publisher Coreには変更がない。
