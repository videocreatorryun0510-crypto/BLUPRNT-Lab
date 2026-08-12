# ADR 0024: Evidence-grounded Candidateを正式Claimから分離する

- Status: Accepted
- Date: 2026-08-13
- Phase: 5.28 Evidence-Grounded Claim Builder MVP

## Context

Phase 5.27でPubMed Formal EvidenceとHuman Selectionが完成した。AIを接続する際、一般医学知識による補完、Evidence外の事実、架空Reference、未承認の正式Claim化を構造的に防ぐ必要がある。

## Decision

1. AI出力は正式Claimではなく`Claim Candidate Contract 1.0`とする。
2. 入力は人が採用したFormal Evidence Selection Setだけとする。
3. Discovery、excluded、pending、未確認URLは型とValidationの両方で拒否する。
4. CandidateごとにEvidence ID、Source Locator、Support Level、Scope、Assessmentを必須にする。
5. AI ConfidenceとEvidence Supportを分離する。
6. UnsupportedとConflictingを隔離し、自動解決・自動採用しない。
7. 重複はPreviewだけ行い、自動Mergeしない。
8. 人の`accepted`かつ`direct`だけをAuthoring Draftへ採用する。
9. Referenceは既存BuilderがFormal Evidence Metadataから生成する。
10. Prompt Builderと後段ContractをProvider非依存とし、Gemini固有処理をAdapter内へ閉じる。
11. Auditへ医学本文とAPI Keyを保存しない。
12. Promotion、Registry、Approval、Knowledge Contractを変更しない。

## Not selected

- LLM出力を直接正式Claimへ登録：人の判断と安定ID発行を迂回する。
- Discovery Candidateから直接生成：DiscoveryとEvidenceの境界を破る。
- AI ConfidenceをEvidence Supportとして利用：異なる概念を混同する。
- Unsupported Claimの自動破棄：問題の可視化とPrompt改善に使えない。
- Conflicting EvidenceのAI自動選択：医学レビュー前に結論を捏造し得る。
- Candidate重複の自動Merge：意味差とRegistry履歴を壊し得る。
- Gemini固有のCandidate JSON：Provider交換時に後段を変更することになる。

## Consequences

正式Evidenceから追跡可能な候補を短時間で得られる一方、Candidateは医学承認ではなく、人の確認と将来のMedical Reviewが必要である。MVPでは修正文のSupport再評価、partialの明示採用、意味ベース重複判定、永続Candidate Set Repositoryを後回しにする。

## Compatibility

Knowledge、Registry、Promotion、Approval Gate、Artifact、Publisher Core、Discovery Candidate、Formal Evidence、PubMed Providerの既存Contractは不変である。Phase 5.24のFixture Claim Builderも互換維持する。
