# ADR 0022: Discovery CandidateをFormal Evidenceから型分離する

- Status: Accepted
- Date: 2026-08-12
- Phase: 5.26.1 Discovery Candidate Boundary

## Context

Phase 5.26はGemini GroundingのCitationを既存Evidence Bundleへ変換した。自動保存・Claim生成は禁止していたが、形式上はClaim Builderが受け取れるため、将来の接続ミスで探索候補が正式根拠として扱われる危険が残った。

## Decision

1. Discoveryは`DiscoveryCandidate`と`DiscoveryCandidateSet`だけを使用する。
2. Discovery ProviderはEvidence Contract、Normalizer、Ranker、Bundle Builderを使用しない。
3. CandidateとSetにClaim、Bundle、Promotion、Registry、Approvalの禁止フラグを`false`固定で持たせる。
4. 型制約に加え、5つの禁止先を実行時Validationでも拒否する。
5. WorkbenchからEvidence Level、Evidence Bundle、Claim、Knowledge表示を削除する。
6. Human Selection後の正式取得は、PubMed等の専用`FormalEvidenceProvider`だけが担当する。
7. Phase 5.26のHTTP URLは互換Aliasとして残すが、Discovery Contract以外は返さない。
8. Knowledge、Promotion、Registry、Approval、Artifact、Renderer、Publisher Coreを変更しない。

## Not selected

- Evidence Bundleへ`is_discovery`を追加する案：同じ型を使うため誤接続を防げない。
- Evidence Level Cとして保存する案：低い正式Evidenceと未取得の探索候補を混同する。
- UI文言だけを変更する案：APIまたは内部処理からの誤接続を止められない。
- GeminiのCitationを人が選べばそのままEvidenceへ昇格する案：専用Providerの取得条件、原典Metadata、利用条件を確認できない。
- 既存Phase 5.26 URLを削除する案：Workbenchや検証手順を不必要に破壊する。

## Consequences

Gemini Groundingは人向け探索に限定され、Claim生成可能な根拠は専用Provider経路だけになる。正式Providerが未実装の間はDiscovery CandidateをEvidenceへ進められないが、これは安全側の意図した停止である。今後はProviderごとの利用条件、ID解決、本文取得範囲、更新・撤回監視を個別に実装する必要がある。

## Compatibility

正式Evidence ContractとEvidence Bundle Contractは不変である。Phase 5.26のAPI Routeと監査履歴はMigration経路で維持する。Responseの意味はDiscoveryへ訂正され、Evidence Bundleを返さない。
