# 検査項目カテゴリ専用テンプレート Version 0.2

この節は`classification.term_type`が`test_item`の場合だけ適用します。

## test_item_contentの必須内容

### purpose

検査の目的を1〜4件。診断名の羅列ではなく、「何を評価する検査か」を書く。

### specimens

検体、採取容器・抗凝固剤、保存・取扱い、国家試験上の注意を分ける。溶血、乳び、黄疸、保存温度など、重要な分析前要因を優先する。

### measurement_methods

国家試験で区別すべき測定方法を1〜6件。JSCC法、IFCC法、酵素法、免疫法、HPLC法など、対象項目に実在する方法だけを書く。

- `method_name`: 方法名
- `standardizing_body`: JSCC、IFCCなど。該当しなければ空文字
- `method_summary`: 方法の特徴と他法との違い
- `exam_focus`: 国家試験で問われる比較点

### measurement_principle

測定方法とは分けて、何を測って値へ変換するかを書く。

- `measured_quantity`: 酵素活性、濃度、吸光度変化など
- `reaction_sequence`: 主反応と必要な共役反応
- `detection_signal`: 吸光度、蛍光、発光、凝集など
- `wavelength_or_endpoint`: 波長または終点。確認できない場合は空文字

### reference_ranges

対象集団、検体、表示値、単位、条件を分ける。すべて`verification_status: requires_source_check`とし、測定法・施設差を明記する。

### high_conditions / low_conditions

代表疾患・状態、上昇または低下する理由を分ける。低値の臨床的意義が乏しい項目では`low_conditions`を空配列にできるが、`low_value_note`へその理由を書く。

### related_test_combinations

2項目以上の組合せと読み方を書く。単なる関連語の列挙ではなく、AST/ALT、AST/LD、AST/ALPのように、組合せで何を判断するかを書く。

### interpretation_cautions

検体不良、薬剤、年齢、性別、日内変動、測定法差、病期など、解釈を誤る原因を2〜8件書く。

### frequent_exam_points

国家試験で問われる測定法、原理、検体、反応、比較、偽高値・偽低値を5〜10件書く。

### comparison_tests

比較対象、比較軸、決定的な違いを分ける。ALT、LD、ALPなど、受験者が混同しやすい検査を優先する。

### exam_keywords

過去問や教科書索引で探せる短い語句を5〜15件書く。

