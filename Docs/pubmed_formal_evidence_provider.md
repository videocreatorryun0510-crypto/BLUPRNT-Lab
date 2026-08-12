# Phase 5.27 PubMed E-utilities Formal Evidence Provider MVP

## 目的

PubMedをBLUPRNT Lab初のFormal Evidence Providerとして接続します。Gemini Discovery CandidateをEvidenceへ変換せず、NCBI公式E-utilitiesへ再問い合わせし、PubMed Recordを確認できた場合だけ既存Evidence Contract 1.0へ標準化します。

```text
医療用語 / Discoveryで人が選んだ候補
  ↓ 検索Hintだけを利用
PubMedEvidenceProvider
  ↓ ESearch（PMID）
NCBI PubMed
  ↓ EFetch XML（正式Metadata）
PubMed Record
  ↓ PubMedEvidenceNormalizer
Normalized Evidence 1.0
  ↓ 既存Deduplicator → Ranker → Bundle Builder
Evidence Bundle 1.0
  ↓
Human Selection（採用 / 除外 / 保留）
```

Claim Builder、Knowledge Draft、Registry、Promotion、Approvalは今回呼びません。

## NCBI公式API

利用先は`https://eutils.ncbi.nlm.nih.gov/entrez/eutils`に固定します。

- ESearch：検索式から最大20件（設定上限30件）のPMIDを取得
- EFetch：PMIDをまとめて1回のXML Requestで取得
- 全文およびPMC Full Textは取得しない
- `tool`と任意の`email`、任意の`api_key`をRequest Parameterへ付与

参照した公式資料：

- [NCBI E-utilities Usage Guidelines](https://www.ncbi.nlm.nih.gov/books/NBK25497/#chapter2.Usage_Guidelines_and_Requirements)
- [E-utilities Parameters and EFetch](https://www.ncbi.nlm.nih.gov/books/NBK25499/)
- [NCBI Policies — E-utilities](https://www.ncbi.nlm.nih.gov/home/about/policies/)

## PubMed Record

Provider内部では次を構造化します。

- PMID、Title、Authors、Journal、Publication Date
- Abstract、DOI、Publication Type、Language、MeSH
- PubMed URL、取得日時

Raw XMLはWorkbench、Claim Builder、Auditへ渡しません。著者、Publication Type、MeSHは既存Evidence Contractを変更しないため、`evidence_id`に紐づくWorkbench用Formal Evidence Metadataとして表示します。

## Evidence Contract Mapping

| PubMed | Evidence Contract 1.0 |
|---|---|
| PMID | `pmid`、`provider_record_id`、安定`evidence_id` |
| Title | `title` |
| Journal | `publisher` |
| Publication Date | `publication_date` |
| Abstract | `abstract_or_snippet` |
| DOI | `doi` |
| Language | `language` |
| PubMed URL | `url` |
| Authors等 | Formal Evidence Metadata Preview |

安定Evidence IDはPMID、DOI、URL、Title＋Publication Dateの順で決めます。DeduplicatorもPMID、DOI、URL、Title類似の順で照合し、CorrectionやErratum等は日付や版の差を無視して統合しません。

## Evidence Level

ProviderはEvidence Levelを決めません。Normalizer側の保守的PolicyがPublication Typeを評価します。

- Guideline / Practice Guideline：B
- Systematic Review / Meta-Analysis：B
- その他・判断不能：C

PubMedに収載されているだけではAにしません。将来、医学レビュー済みPolicy Registryへ分離するまでは安全側の評価です。

## Discovery Handoff

Discovery Candidateに含まれるPMID、DOI、Title、元の検索語は検索Hintに限って使用します。PubMedへESearchし、PubMed自身から返ったPMIDをEFetchできた場合だけEvidenceになります。

```text
Discovery Candidate ≠ PubMed Evidence
Candidate → PubMed再検索 → PubMed Record確認 → Evidence
```

PubMedで見つからないCandidateは`empty_result`または`pmid_not_found`で停止します。

## Human Selection

Formal Evidenceごとに次を追記専用JSONLへ保存します。

- Evidence ID、Bundle ID
- 採用・除外・保留
- 操作者、日時、任意コメント

これは「将来Claim生成へ使う候補」の選択で、医学レビュー・承認ではありません。KnowledgeやRegistryは変更しません。

## Rate LimitとSecret

- API Keyなし：0.34秒以上の間隔（毎秒3回未満）
- API Keyあり：0.11秒以上の間隔（毎秒10回未満）
- 1テーマ最大20件、設定可能な絶対上限30件
- ESearchとEFetchは各1回、RetryはTimeout・429・5xx・Network時に最大1回
- API Keyは`.env`だけで管理し、画面・監査・エラーへ値を出さない

## Partial Success

EFetch内の一部Recordだけが不正な場合、正常RecordをEvidence Bundleへ通し、不正PMID・不足PMIDをExecution Metadataへ記録して`partial_success`とします。全件が不正なら失敗します。壊れたRecordを推測補完しません。

## AuditとCache

Search AuditはQuery、PMID、件数、所要時間、Retry、API Key使用有無、Rate Limit Mode、Error Codeだけを保存します。Abstract、Raw XML、API Key値は保存しません。

Cacheは交換可能な`PubMedRecordCache`境界とNull実装だけを用意しました。MVPでは永続Cacheを実装せず、Evidence正本と混同しません。

## Workbench

AI Knowledge Wizard内でDiscoveryと別セクションに表示します。

- 医療用語から「PubMed正式Evidence検索」
- Discovery Candidateから「PubMedで正式Evidence取得」
- PMID、Title、Authors、Journal、Publication Date、Publication Type、DOI、Abstract有無、Evidence Level、取得日時
- Evidence Bundle、Fingerprint
- 採用・除外・保留

画面には常に`Formal Evidence: Yes / Claim Generated: No / Knowledge Draft: No / Registry Changed: No / Promotion: No`を表示します。

## 実API受入試験（2026-08-12）

大量取得を避け、公式E-utilitiesへ最初に1件だけ接続した後、最大3件の小規模Pilotを実施しました。

| 入力 | Query | 取得PMID | 件数 | Abstractあり | 結果 |
|---|---|---|---:|---:|---|
| Ferritin | `"Ferritin"[Title/Abstract]` | 33881539 | 1 | 1 | 成功 |
| Iron deficiency anemia | `"Iron deficiency anemia"[Title/Abstract]` | 25946282 / 40603791 / 26222573 | 3 | 1 | 成功 |
| Gram stain | `"Gram stain"[Title/Abstract]` | 19885931 / 14925025 / 27815540 | 3 | 1 | 成功 |

各検索はESearchとEFetchの2 Requestで完了し、API Keyなしの安全側Limiterを利用しました。Ferritin 1件でHuman Selectionの`hold`保存も確認しました。結果は接続確認用であり、医学承認は行っていません。Claim生成とRegistry更新はいずれも0件です。
