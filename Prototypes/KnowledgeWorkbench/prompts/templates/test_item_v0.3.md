# 検査項目カテゴリ専用テンプレート Version 0.3

この節は`classification.term_type`が`test_item`の場合だけ適用します。

## purposes

検査の目的を医学的事実として書きます。学習上の重要性や覚え方は書きません。

## specimens

検体、容器・抗凝固剤、取扱い、安定性を分けます。不明な値を推測せず、確認が必要な場合は空文字にできます。

## measurement_methods

対象項目に実在する測定方法だけを書きます。JSCC、IFCC、HPLC、免疫法など、方法名と標準化団体と事実説明を分けます。

国家試験で複数の測定方法の比較が必要な検査項目では、代表的な方法を1つだけに省略しないでください。ASTではJSCC標準化対応法とIFCC法を別々の`measurement_methods`として保持します。HbA1cでは、HPLC法、免疫法、酵素法などの代表的方法を、実在する範囲で別々に保持します。

## measurement_principles

測定方法とは別に、測定対象、反応、検出信号、波長・終点を記録します。

`related_method_names`には、`measurement_methods.method_name`に出力した文字列と完全に同じ方法名だけを入れてください。対応する方法が特定できない場合は空配列にします。

## value_associations

高値・低値のそれぞれで、病態と代表疾患を分けます。

- `pathophysiologic_states`：肝細胞障害、筋障害、赤血球寿命短縮など
- `representative_diseases`：急性肝炎、横紋筋融解症、溶血性貧血など
- `interpretive_notes`：高値・低値の医学的解釈に必要な事実

病態名を代表疾患へ、疾患名を病態へ混ぜないでください。意義が乏しい側は空配列にできます。

## related_test_combinations

関連検査名と、組み合わせから分かる医学的事実を記録します。試験対策上の助言は書きません。

## interpretation_cautions

溶血、保存条件、測定法差、病期など、結果解釈に影響する医学的事実を書きます。
