# Knowledge JSON Version 1.0 設計サンプル

このフォルダは、Version 1.0のカテゴリ別テンプレートと完全性評価結果を確認するためのサンプルです。

- `test_item`、`staining_method`、`specimen`、`reagent`、`biological_structure`、`disease`、`laboratory_test_item`はSchema実装済みです
- `staining-method.example.json`、`specimen.example.json`、`disease.example.json`、`laboratory-test-item.example.json`等はWorkbenchの正式下書きです
- `disease-condition.example.json`はVersion 1.0設計時点の歴史的サンプルです。正式疾患Categoryの例は`disease.example.json`を使用します
- 微生物、寄生虫は設計サンプルであり正式Category未実装です
- 医学的内容は未監修です
- evidenceが空のclaimは承認済み正本として使用できません
- JSON内に表示文章、PDFレイアウト、動画演出、問題文は含めません

ファイル：

- disease-condition.example.json
- disease.example.json
- laboratory-test-item.example.json
- microorganism.example.json
- parasite.example.json
- staining-method.example.json
- specimen.example.json
- completeness-assessment.example.json

詳細は ../../knowledge_json_v1.0_category_design.md を参照してください。
