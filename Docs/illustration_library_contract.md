# Illustration Library 接続仕様（Phase 3.3設計）

## 1. 目的

Illustration Libraryは、`organ.liver`、`cell.rbc`、`device.microscope`等の安定したIDから、再利用可能な図素材を取得する将来コンポーネントです。Phase 3.3ではLibrary本体や素材を作らず、Visual Grammarから安全に接続する契約だけを定義します。

## 2. 接続フロー

```text
Diagram Intent
  - Illustration Category
        ↓
Visual Grammar
  Illustration Slot
  - accepted_asset_namespaces
  - preferred_asset_ids
  - missing_asset_policy
        ↓
Illustration Resolver（将来）
        ↓
Asset Reference（将来）
  - illustration_id
  - version
  - file / URI
  - format
  - content_hash
  - license
  - accessibility metadata
        ↓
Diagram Renderer（将来）
```

## 3. 責務

### Visual Grammar

- どのNodeにIllustrationが使えるかを`slot_id`で示す
- 使用可能なNamespaceと希望IDを示す
- 素材がない場合の意味的fallbackを示す

### Diagram Intent

- 図の意味としてOrgan、Cell、Instrument、Molecule等のどのCategoryが必要かを示す
- 個別のIllustration IDやファイルは指定しない

### Illustration Library

- Illustration IDと版の一意性を保証する
- 実ファイル、Hash、形式、権利、廃止状態を管理する
- 媒体やRendererが使える候補を返す

### Renderer

- Themeに従って素材を表示する
- 素材がない場合に基本図形、ラベルのみ、省略を適用する
- 出力媒体に適さない形式を変換または拒否する

## 4. Phase 3.3の固定ルール

- Knowledge JSONへ画像・Illustration ID・ファイルPathを保存しない
- Visual Grammarへ画像本体、色、線幅、座標を保存しない
- `illustration.resolve_by_id`をProvider非依存のCapability IDとする
- Namespaceは`organ`、`cell`、`molecule`、`enzyme`、`sample`、`device`、`icon`、`bacteria`、`parasite`、`laboratory_test`から開始する
- 必須素材がない場合も、Library実装前は基本図形またはラベルで代替できる

## 5. Library実装時に決める事項

- ID命名とAlias／deprecated運用
- SVG、PNG、動画素材等の対応形式
- ライセンス、出典、作成者、利用範囲
- Asset Version、Hash、差分、Backup
- 日本語・英語ラベルと代替テキスト
- Media Profile別の最適Variant
- 人体・病理・微生物等の医学監修フロー

これらは実素材の運用要件が確定してから設計します。Phase 3.3で先に固定すると、利用する制作ツールや権利条件を誤って制限するためです。
