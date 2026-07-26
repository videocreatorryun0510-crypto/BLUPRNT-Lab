# Diagram Taxonomy Contract Version 1.0

## 1. 目的

Diagram Taxonomyは、BLUPRNT Labが扱う医学図解を永続IDで分類するPublisher Coreの共通辞書です。医学知識、教育順、描画命令、AI Promptではありません。

```text
Knowledge JSON（医学的事実）
        ↓ 読取専用
Diagram Taxonomy（図解分類の共通辞書）
        ├─ Diagram IntentはTaxonomy IDだけを参照
        └─ Visual Grammarは対応可能なTaxonomy IDだけを参照
        ↓
Semantic Blueprint（分類を引き継いだ意味構造）
```

## 2. 階層モデル

Taxonomyは、各Nodeが`parent_taxonomy_id`を持つ平坦な台帳として保存します。JSONの深い入れ子にしないため、1000件以上へ増えてもID検索、親子検証、差分確認を同じ方法で行えます。

各Nodeは次を持ちます。

| 項目 | 役割 |
|---|---|
| `taxonomy_id` | 意味が変わらない永続ID |
| `parent_taxonomy_id` | 1つ上の分類。Rootでは`null` |
| `canonical_name` | 現在の標準表示名 |
| `aliases` | 検索・旧称対応用の別名 |
| `intent_type` | Rootだけが持つ後方互換用の大分類 |
| `status` | `active`または`deprecated` |
| `replacement_taxonomy_id` | 廃止後の移行先 |

`intent_type`による分類判断はDiagram Intentへ保存しません。TaxonomyのRootから解決します。

## 3. 永続IDルール

- `taxonomy_id`は表示名を変更しても変更しない
- 既存IDを別の意味に再利用しない
- 不要になったNodeは削除せず`deprecated`へ変更する
- 移行先がある場合は`replacement_taxonomy_id`を指定する
- 同じVersionのTaxonomyを上書きせず、新しいVersionを追加する

## 4. 検証

読み込み時に次を拒否します。

- `taxonomy_id`重複
- 存在しない親ID
- 親子循環
- Root以外の`intent_type`
- Active Nodeの置換先指定
- 存在しない置換先
- Diagram Intentによる未知・廃止ID参照
- Visual Grammarによる未知・廃止ID参照
- Intentの分類とGrammarの対応階層が一致しない組合せ

Visual GrammarはIntentのTaxonomy IDと同じNodeだけでなく、その祖先Nodeを参照できます。これにより「Enzyme Assay用の共通Grammar」をUV Absorbance、Colorimetric、Fluorescenceへ再利用できます。

## 5. Diagram Intentとの接続

Taxonomy対応Diagram Intent 1.1は`taxonomy_id`だけを保持し、`intent_type`を保持しません。Publication PlannerがTaxonomyからRootまでのPathと大分類を解決します。

旧Diagram Intent 1.0は過去Planの再現用に残します。既存Profileを書き換えず、Template 1.5から新契約を利用します。

## 6. Visual Grammarとの接続

Taxonomy対応Visual Grammar 1.1は、各Grammar Ruleに対応可能な`taxonomy_ids`だけを持ちます。親子判定、分類、廃止判定はTaxonomyとTemplate Registryが担当し、Grammar自身は分類ロジックを持ちません。

## 7. ASTサンプル

```text
taxonomy.measurement
Measurement Principle
  └─ taxonomy.measurement.enzyme
     Enzyme Assay
       └─ taxonomy.measurement.enzyme.absorbance
          UV Absorbance
```

ASTのDiagram Intentは`taxonomy.measurement.enzyme.absorbance`だけを参照します。解決後のPublication Plan 1.4とSemantic Blueprint 1.1には、再現可能なTaxonomy VersionとPathが含まれます。

## 8. 保持しない情報

- 医学本文とClaim
- 医学用語そのもののカテゴリ
- 教育順と難易度
- Node、Connector、構図
- 色、フォント、座標
- SVG、画像、AI Prompt
- RendererやProviderの選択

Diagram Taxonomyは「図解を何種類に分けるか」だけを管理します。
