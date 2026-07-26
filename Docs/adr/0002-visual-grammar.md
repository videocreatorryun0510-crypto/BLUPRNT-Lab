# ADR 0002: Visual Grammarを描画エンジン非依存の共通言語にする

- 状態: Accepted
- 日付: 2026-07-17
- 対象: Phase 3.3

## 背景

Visual Profileは「何を図にするか」を選べますが、図の内部をどう構成するかを統一できませんでした。AI画像、SVG、Mermaid、Illustrator、PowerPoint等が個別に構図を判断すると、媒体・Provider・制作回ごとに図解が変わり、レビューと再利用が困難になります。

## 採用した設計

Visual GrammarをPublisher Coreの独立した版付きProfileとして追加します。

- Visual Profileは図解種別と参照Claimを選ぶ
- Visual GrammarはComposition、Node、Connector、Label、意味的Highlight、Densityを決める
- Themeは色、フォント、余白、線を決める
- Layoutは図の外側の配置を決める
- Illustration Libraryとは安定したAsset IDを解決する契約だけを持つ
- Publication Plan 1.2へ各Visualの解決済みGrammarを固定する
- Publication Plan 1.0／1.1を後方互換として残す

Highlightは`exam_frequent`、`important`、`warning`、`positive`、`negative`という意味だけを持ちます。同じ意味をPDFでは枠、動画ではテロップ、白黒印刷ではパターン等へ変換する責務はThemeとRendererに置きます。

## 採用しなかった設計

### Knowledge JSONへ図解構造を保存する

医学的事実と表現方法が混ざり、同じKnowledgeを別用途へ再利用できなくなるため採用しません。

### Visual Profileへ構図を直接追加する

「何を描くか」と「どう描くか」が一体化し、複数媒体・複数図解で共通文法を再利用しにくいため採用しません。

### Themeへ図解構造を保存する

ブランド変更で医学図解の意味構造まで変わるため採用しません。

### Layoutへ図の内部座標を保存する

ページ上の配置と図の内部構造が混ざり、A4、動画、SNSへの展開が困難になるため採用しません。

### AI Promptを図解仕様の正本にする

Providerごとの解釈差、モデル更新、文章表現の揺れで再現性が失われるため採用しません。

## 結果

同じVisual Grammarを異なるRendererが読み、媒体に合った表現へ変換できます。Providerを交換しても、BLUPRNT Labが定義する図解の意味と構造は維持されます。

## 将来変更する可能性

- Node・Connector・Diagram Typeの共通Taxonomy Registry
- Claimを個別Nodeへ解決するDiagram Blueprint
- Illustration LibraryのAsset版、Hash、ライセンス、代替テキスト
- 媒体能力に応じたGrammar fallback
- Visual Grammarの承認・差分レビュー画面
