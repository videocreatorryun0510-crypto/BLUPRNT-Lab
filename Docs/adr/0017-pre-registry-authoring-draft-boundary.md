# ADR 0017: 未完成Knowledgeを正式Registryから分離したAuthoring Draftとして保存する

- Status: Accepted
- Date: 2026-08-06
- Phase: 5.22 Knowledge Authoring Workflow MVP

## Context

Knowledgeを1000件以上へ増やすには、人が短時間でSkeleton、Claim、Referenceを作れる画面が必要である。一方、既存Knowledge Registryは安定ID、版、承認、履歴を持つ正式なSingle Source of Truthであり、入力途中の空Claimや未接続Referenceを直接保存すると、承認対象と作業途中データの境界が曖昧になる。

既存Knowledge ContractはCategoryごとに事実の保存先を厳格に定める。短時間入力の最中から各ClaimをCategory専用構造へ配置すると、作成者の操作量と画面の複雑さが増える。

## Decision

1. 入力途中のデータをWorkbench所有の`KnowledgeAuthoringDraft 1.0`として正式Registryから分離する。
2. Draft内の`knowledge`には既存Knowledge Contract 1.0へ適合する空Skeletonを保存する。
3. 入力中のClaim、Reference、Relation、ReviewをAuthoring Wrapperへ保存し、Knowledge Contractを変更しない。
4. Reviewは常に`draft`、医学監修実施は常に`false`とする。
5. DifficultyとExam ImportanceはAuthoring Metadataとし、根拠のない正式Exam Metadataを生成しない。
6. Authoring DraftはRepository Interface越しに、Git対象外の独立JSONファイルへ原子的に保存する。
7. JSON Importは検証後に新しい`draft_id`を発行し、正式Registryを変更しない。
8. Authoring Completenessを作業進捗として扱い、Knowledge Completenessや医学品質と明確に区別する。

## Reasons

- 未完成KnowledgeがApproval GateやPublisherへ流れることを構造的に防げる
- Knowledge、Registry、Claim、Relation、Artifactの既存Contractを変更せず導入できる
- 作成者は1 Claim 1事実と出典対応へ集中できる
- ファイル保存からSQLiteや外部DBへRepositoryだけを交換できる
- Import/Exportと自動テストを正式Registryから隔離して実施できる

## Rejected

- 空のKnowledgeを直接Knowledge Registryへ保存する案
- Category SchemaへAuthoring専用の任意欄を追加する案
- Claim入力のたびにRegistry Claim Dictionaryへ正式登録する案
- Difficultyと手入力Importanceを正式Exam Metadataへ保存する案
- JSON Editorだけを提供し、人にIDや構造を手入力させる案
- AIでSkeleton本文を自動生成する案

## Consequences

正式運用へ進めるには、Authoring ClaimをCategory専用Knowledge構造へ割り当て、Claim Dictionaryと照合し、ReferenceをEvidenceへ変換するPromotion Mapperが別途必要になる。複数下書きが同じ`knowledge_id`を持つ可能性があるため、Promotion時に競合を検出しなければならない。

この追加作業は意図的である。Phase 5.22は作成速度を改善するMVPであり、正式登録・医学レビュー・承認を迂回しないことを優先する。

## Compatibility

Knowledge Contract、Registry、Claim、Relation、Approval Gate、Source Bundle、Presentation Artifact、Publisher Coreへの破壊的変更はない。Authoring APIとDraft ContractはWorkbench内の追加機能である。
