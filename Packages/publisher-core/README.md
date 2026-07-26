# BLUPRNT Publisher Core

`publisher-core`は、承認済みKnowledge JSON・Exam Metadata・Knowledge Registryを、PDF、note、TrainingVideo、NationalExamへ渡す前に、**媒体に依存しないPublication Plan**へ組み立てる共通基盤です。

Phase 3.0では設計と計画生成だけを扱います。PDF、記事、動画、問題、SVG、Mermaid、画像はまだ生成しません。

## 守る境界

```text
Knowledge JSON ─┐
Exam Metadata ──┼─→ PublicationSourceBundle（読取専用）
Registry ───────┘
                         ↓
Content → Education → Visual → Visual Grammar ↔ Diagram Taxonomy ↔ Diagram Intent → Claim Mapping → Semantic Blueprint
                         ↓                 ↑
                   Design System     Template Registry
                         ↓
                  Publication Plan
                         ↓
        Publisher Adapter（Phase 3.1以降）
```

- 医学的事実は追加・修正・要約しない
- `approved`のKnowledgeとClaimだけを使用する
- Publication PlanにはClaim本文ではなく`claim_id`、`claim_key`、版を保存する
- Profileは不変・版付きで、同じVersionをその場で書き換えない
- 外部AI、PDF、動画ライブラリをCoreモデルへ混ぜない

## Profileの責務

| 層 | 決めること | 決めないこと |
|---|---|---|
| Content Profile | 掲載するClaim・Exam項目・セクション | 位置、色、文章表現 |
| Education Profile | 学習目的、難易度、教育順、試験強調、比較・図解優先、教育ブロック | 医学的事実、完成文章、色、物理配置 |
| Visual Profile | どのClaimをどの図解種別で表すか | 実画像、医学知識、配置 |
| Visual Grammar | 図の内部構図、Node、Connector、Label、意味的な強調、Density | 色、フォント、線、外部配置、完成画像 |
| Diagram Taxonomy | 永続ID、親子階層、名称、別名、廃止・置換 | 医学本文、教育順、構図、描画 |
| Diagram Intent | Taxonomy ID、図の教育目的、意味順、必須概念、Claim選択方針、Illustration Category | 分類ロジック、医学本文、Claim割り当て結果、構図、画像、Prompt |
| Claim Mapping Resolver | 明示規則に一致する承認済みClaimをConceptへ割り当てる | 本文推測、AI補完、未承認Claim利用 |
| Semantic Blueprint | Claim参照、Concept、意味順、Semantic Relation、不足Concept | 座標、色、フォント、SVG、Prompt |
| Layout Profile | セクション・図解を置く領域と順序 | 色、フォント、物理寸法 |
| Theme | 色、フォント、余白トークン、アイコン、枠、見出し、テロップ、キャラクター | 医学知識、掲載項目、構図 |
| Design System | シリーズで固定するTheme、Layout、部品Variant | 個別テーマの医学内容 |
| Template Registry | 用途・VersionごとのProfile組合せ | 成果物生成 |

## 実装済みの接続口

- `PublisherPlanner`：Profileと承認済みデータからPublication Planを作る
- `TemplateRegistry`：版付きProfileを解決し、参照切れとシリーズ逸脱を拒否する
- `PublisherAdapter`：将来のPDF、note、Video、Exam出力共通Interface
- `VisualGenerationProvider`：将来のGPT Image、Gemini、ImageFX、Napkin、SVG Generator等の共通Interface

Visual Grammarは画像生成AIへのPromptではなく、BLUPRNT Lab共通の図解言語です。描画エンジンがSVG、AI画像、Mermaid、PowerPoint等へ変わっても、同じDiagram Type、Composition、Node、Connector、Label、Highlight、Densityを読める契約にしています。

Diagram IntentもAI Promptではありません。Taxonomy IDと、`sample → reaction → detection → result`等の概念列で図が伝える意味を表します。大分類はTaxonomyのRootから解決し、Intent自身は分類判断を行いません。

Phase 3.5では、この割り当てを行うClaim Mapping ResolverとSemantic Blueprintを追加しました。ResolverはClaim本文を読みません。IntentのPrefix規則、承認状態、Exam Priorityの順位だけを使い、一致しないConceptは不足として残します。

Phase 3.6では、図解分類をDiagram Taxonomyへ分離しました。Taxonomy対応Diagram Intentは`intent_type`を直接持たず、`taxonomy_id`だけを参照します。Visual Grammarも対応可能なTaxonomy IDだけを持ち、親子判定や分類はTemplate Registryが行います。

Visual ProfileはAI名ではなく`capability_id`を主契約にします。`preferred_provider_ids`は優先候補にすぎず、Provider固有パラメータをProfileへ保存しません。

## 同梱Profile

`profiles/`にはASTと、Phase 4.1のGram染色Vertical Slice用定義があります。

- Content：国家試験PDF、note、TrainingVideo、NationalExam
- Education：国家試験対策Version 1（Standard）
- Visual：reaction diagram、organ distribution、comparison table、flowchart
- Visual Grammar：ASTのreaction diagram、comparison table、disease mechanism
- Diagram Taxonomy：測定法、検査工程、病態、比較の永続ID階層
- Diagram Intent：ASTのUV Absorbance、検査項目比較、Biomarker Release分類
- Layout：4媒体の抽象配置
- Theme：BLUPRNT国家試験シリーズ
- Design System：4媒体で共通するシリーズ規則
- Templates：4媒体各Version 1

Gram染色では既存Profile契約を変更せず、国家試験PDF向けContent、Education、Visual、Visual Grammar、Diagram Intent、Templateを追加しました。既存の`taxonomy.workflow.staining.gram`、A4 Layout、Theme、Design Systemを再利用し、染色工程とGram陽性／陰性比較をPublication Planへ組み立てられます。これは互換性検証用であり、医学監修済み教材ではありません。

これらは医学監修済み成果物ではなく、Publisher Architectureの構造確認用です。

## Media Profile拡張点

`TemplateDefinition`と`PublicationPlan`には、未使用の`media_profile_ref`があります。Phase 3.0ではMedia Profileモデルも解決処理も実装しません。将来、A4縦、スマホ縦、Instagram、Reels、note埋込などの物理条件をこの参照先へ追加し、Content・Education・Visual・Layout・Themeを変更せず媒体寸法を吸収します。

詳細は[Publisher Architecture](/Users/ryuseiito/Documents/BLUPRNT%20Lab/BLUPRNT%20Lab/Docs/publisher_architecture.md)を参照してください。

## テスト

```bash
PYTHONPATH="Packages/knowledge-contracts/src:Packages/publisher-core/src" \
  .venv/bin/pytest Packages/publisher-core/tests
```
