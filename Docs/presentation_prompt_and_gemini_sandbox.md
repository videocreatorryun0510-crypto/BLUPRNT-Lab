# Phase 5.18 Presentation Prompt Builder & Gemini Adapter Sandbox

## 目的

Provider PayloadをGeminiへ直接渡さず、Provider非依存のPresentation Promptを経由します。Gemini固有のAPI・モデル・Prompt変換はAdapter内部だけに閉じ込めます。

```text
Provider Payload
    ↓
Presentation Prompt Builder（Provider非依存）
    ↓
Presentation Prompt 1.0
    ↓
Gemini Sandbox Adapter（Gemini固有）
    ↓
Interactions API / store=false
    ↓
Response Mapper
    ↓
Traceable Response 1.0（既存Contract）
```

## Presentation Prompt 1.0

保持する情報：

- 学習目的、対象者、タイトル
- 承認済みClaimのID・Key・無変更本文
- Key Message、Diagram Request、Reference
- Content、Layout、Validation Policy
- Payload / Prompt Fingerprint

Provider名、API URL、SDK、認証方式、Gemini固有命令は保持しません。

## Gemini Sandbox

- Gemini Interactions APIを利用する
- Provider側の会話保存を`store=false`で停止する
- `GEMINI_API_KEY`は`.env`からのみ読む
- APIキー、Gemini Prompt、Provider生レスポンスを監査ログへ保存しない
- Timeout、Network、429、5xxは最大1回だけ再試行する
- 401/403、JSON不正、Approval不一致、Fingerprint不一致は再試行しない
- Structured OutputはClaim・図解・出典IDと件数だけを返す
- 医学本文はTraceable Responseへ保存しない

## Cost

Token数はProvider Responseから取得します。料金はモデルごとに変更されるためコードへ固定せず、次の任意環境変数が設定された場合だけ概算します。

- `GEMINI_INPUT_COST_PER_MILLION_TOKENS`
- `GEMINI_OUTPUT_COST_PER_MILLION_TOKENS`

## Workbench

1. 承認済みKnowledgeからExternal Presentation Requestを生成
2. Provider Payloadを生成
3. Presentation Prompt PreviewでProvider非依存JSONを確認
4. Gemini Sandboxを実行
5. Token、所要時間、Fingerprint、Validation、停止理由を確認

未承認、Preview Mode、APIキー未設定、Fingerprint不一致では外部送信しません。
