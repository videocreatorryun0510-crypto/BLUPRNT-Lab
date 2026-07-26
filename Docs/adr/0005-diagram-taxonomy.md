# ADR 0005: Diagram分類を版付きTaxonomyへ分離する

- 状態: 採用
- 対象: Phase 3.6
- 日付: 2026-07-18

## 背景

Diagram Intentが`measurement_principle`等の大分類を直接持つ構造では、1000以上の医学用語に対して測定技術、染色法、病態型等の細分類を一貫して扱えません。IntentやRendererごとに分類判断を実装すると、同じ図解が異なる名前・構造へ分岐します。

## 決定

- Diagram TaxonomyをPublisher Coreの独立・版付きコンポーネントにする
- Nodeは永続`taxonomy_id`と`parent_taxonomy_id`を持つ平坦な台帳にする
- Diagram Intent 1.1は`taxonomy_id`だけを参照する
- Visual Grammar 1.1は対応可能なTaxonomy IDだけを参照する
- 親子関係、循環、廃止、参照整合性はTaxonomyとTemplate Registryで検証する
- Publication Plan 1.4で解決済みPathを固定する
- Knowledge JSONは変更しない
- 旧Intent、Grammar、Publication Planを読み続けられるようVersionを並存させる

## 採用しなかった案

### Diagram Intentへ階層を直接保存する

同じ分類が用語ごとに複製され、名称変更や追加時に大量修正が必要になるため採用しません。

### Visual Grammarが分類規則を持つ

描画構造と分類責務が混ざり、Renderer交換時の再利用性が下がるため採用しません。

### 入れ子JSONだけで階層を表す

1000件以上で差分、検索、親変更、循環検出が扱いにくくなるため、親ID方式を採用します。

### 医療用語カテゴリをKnowledge JSONへ追加する

今回分類するのは医学知識ではなく図解方式です。Knowledgeの正本へPublisher都合の分類を混ぜないため採用しません。

## 影響

- Template RegistryがTaxonomy参照を解決・検証する
- Taxonomy対応TemplateはPublication Plan 1.4を生成する
- Semantic Blueprint 1.1がTaxonomy参照とPathを引き継ぐ
- 将来Nodeを移動・廃止する際の互換ルールと移行ツールが必要になる
