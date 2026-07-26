# PDF Publisher Adapter

BLUPRNT Lab Phase 3.1のA4 PDF出力アダプターです。

Publisher Coreが作成したPublication Planを読み、承認済みのKnowledge Sourceを参照して、
国家試験PDF Version 1を一枚生成します。医学知識の追加・要約・書き換えは行いません。

## Phase 3.1の処理

```text
Publication Plan
  -> Publication Plan Reader
  -> PDF Render Plan
  -> Layout Engine
  -> Theme Engine
  -> Placeholder Visual Renderer
  -> A4 PDF Export
```

- `Publication Plan Reader`: Claim参照を固定されたSource Snapshotから解決します。
- `Layout Engine`: Layout Profileの配置指定をA4 Version 1の座標へ変換します。
- `Theme Engine`: Themeの色・余白をPDF用トークンへ変換します。
- `Placeholder Visual Renderer`: 図解予定位置へ明示的な仮枠を描きます。
- `PDF Export`: 1ページだけを書き出し、内容が枠を超えた場合は失敗させます。

## ASTレビューPDFの生成

リポジトリのPython環境へ依存関係を入れた後、リポジトリ直下で実行します。

```bash
PYTHONPATH=Publishers/PDFPublisher/src:Packages/publisher-core/src:Packages/knowledge-contracts/src \
python Publishers/PDFPublisher/scripts/generate_ast_review_pdf.py
```

生成物はリポジトリ直下の`output/pdf/`へ保存されます。

- `ast_national_exam_v1.plan.json`: 媒体共通のPublication Plan
- `ast_national_exam_v1.render-plan.json`: PDF用に解決した表示データ
- `ast_national_exam_v1.pdf`: プロダクトオーナー確認用PDF

`samples/ast_publication_source.json`は構造・レイアウト確認専用の固定サンプルです。
正式な医学監修済みデータではありません。

## Phase 3.1で意図的に行わないこと

- 図解・画像・SVG・Mermaidの生成
- GPT Image、Gemini、ImageFX等への接続
- Knowledge JSON、Exam Metadata、Registryの変更
- 複数ページへの自動退避

一枚へ収まらない場合は小さな文字で無理に押し込まず、エラーとして検出します。
