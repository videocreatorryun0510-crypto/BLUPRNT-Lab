# ADR 0008: Presentation RequestをAI非依存の独立Contractにする

- 状態: 採用
- 日付: 2026-07-27
- 対象: Phase 5.15 Presentation Contract MVP

## 背景

Source Bundleは教育内容を表すが、成果物の種類、媒体条件、許可する変更、安全検証条件は
表さない。これらをGemini用Promptへ直接埋め込むと、AI提供者を変更するたびに医学的安全
ルールと追跡方法が分岐する。

## 決定

Source BundleとPresentation Engine Adapterの間に、独立したPresentation Request
Contract Version 1.0を置く。

- Presentation TypeとOutput Formatを分離する
- Knowledge固有情報を持たない版付きPresentation Profileを使う
- Claim本文を複製せず、Claim・Diagram・Reference IDとFingerprintを参照する
- PreviewとExternalを明示的に分離する
- Externalは既存Approval Gateの`can_send_to_external_ai()`を必ず通す
- Registry最新版との版・Fingerprint・承認状態・Review Version不一致を停止する
- Builderは医学的文章を生成・変更しない
- Publisher Core、Knowledge JSON、Registry、Source Bundle Version 1.0を変更しない

## 採用しなかった案

### Source BundleからGemini Promptを直接生成する

提供者固有仕様と医学的安全ルールが混在し、Claude、OpenAI、Canva等への交換が難しく
なるため採用しない。

### Source Bundle全文をPresentation Requestへ複製する

教育データの正本が二重化し、訂正・承認・出典追跡の境界が曖昧になるため採用しない。

### Workbench画面だけでExternal利用を停止する

将来のAPI・バッチ・別Adapterから回避できるため採用しない。Builderと既存Approval
Gateの両方で強制する。

### Presentation ProfileへKnowledge固有の医学情報を保存する

Profileの再利用性を失い、医学的事実の正本が分散するため採用しない。

## 影響

- 新しいPresentation Request BuilderをSource Bundle Publisherとは別パッケージにする
- Profile、Contract、Validator、Writer、Auditを独立して版管理する
- 次PhaseのPresentation Engine AdapterはRequestだけを入力契約として利用できる
- Profileの選択権限、Request成果物の世代管理、外部AI応答検証は将来Phaseで追加する
