# ADR 0023: PubMedを最初のFormal Evidence Providerとする

- Status: Accepted
- Date: 2026-08-12
- Phase: 5.27 PubMed E-utilities Formal Evidence Provider MVP

## Context

Phase 5.26.1でDiscovery CandidateをEvidence Bundleから分離した。Claim生成へ利用可能な正式根拠を得るには、利用条件と識別子が明確な専用Providerが必要である。

## Decision

1. PubMed E-utilitiesを最初のFormal Evidence Providerとする。
2. ESearchでPMIDを得た後、EFetch XMLでPubMed Recordを再確認する。
3. Discovery Candidateは検索Hintとしてのみ使い、Evidenceへ直接変換しない。
4. Provider固有XMLはProvider内部へ閉じ、既存Evidence ContractへNormalizerで変換する。
5. Publication Type等の原Metadataは保持するが、ProviderはEvidence Levelを決めない。
6. 既存Deduplicator、Ranker、Evidence Bundle Builderを再利用する。
7. Human Selectionを医学レビュー・Approvalから分離する。
8. NCBI公式Rate Limitより安全側の内部Limiterを適用する。
9. Raw XML、Abstract、SecretをAuditへ保存しない。
10. Knowledge、Promotion、Registry、Approval、Artifact、Rendererを変更しない。

## Not selected

- PubMed検索結果ページのスクレイピング：非公式で壊れやすい。
- Gemini CitationのPubMed Evidence化：PubMed Recordの存在を保証できない。
- PubMed収載だけでEvidence Level A/Bを付与：研究デザインと質を混同する。
- PMC全文を同時取得：利用条件と責務が異なる。
- LLMによる日英Query翻訳：確証のない検索語拡張になる。
- Provider内部からClaimを生成：Evidence取得とClaim Support Assessmentが混ざる。
- Evidence ContractへPubMed専用項目を追加：Provider Neutral性を失う。

## Consequences

正式Evidenceの最初のEnd-to-End経路が完成する。今後PMDAや厚労省を追加してもEvidence Intelligence後段を再利用できる。一方、Evidence Contract 1.0に著者・Publication Type・MeSHの共通欄がないため、MVPは補助Metadata Viewを使う。正式なContract拡張は全Providerを比較してVersion 2で判断する。

## Compatibility

Evidence Contract、Evidence Bundle、Knowledge Contract、Discovery Contractは不変である。Phase 5.25のローカルFixtureとPhase 5.26.1のDiscovery APIは維持される。
