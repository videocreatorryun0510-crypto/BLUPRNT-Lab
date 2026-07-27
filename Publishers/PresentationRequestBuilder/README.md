# Presentation Request Builder

Source Bundleを、外部のPresentation Engineへ渡す生成条件だけを持つ
Presentation Request JSON Version 1.0へ変換します。

```text
Knowledge Registry
        ↓
Source Bundle Publisher
        ↓
Approval Gate
        ↓
Presentation Request Builder
        ↓（次Phase以降）
Presentation Engine Adapter
```

医学的事実の正本はRegistry、教育用中間データの正本はSource Bundleです。
Presentation RequestはClaim本文を複製せず、Claim ID、Diagram Request ID、
Reference ID、Source Fingerprintを参照します。

MVPで実際に生成できる組み合わせは次の1種類です。

- Presentation Type: `presentation_document`
- Output Format: `structured_json`
- Profile: `presentation_document_basic_v1` Version `1.0`

Preview Requestは`draft`、`owner_review`、`medical_review`、`approved`から生成できます。
External Requestは既存Approval Gateを必ず通り、`approved`だけが生成できます。
`published`と`deprecated`は現行方針では停止します。

生成物は次へ安全な一時ファイル置換で保存します。

```text
Publisher Output/presentation_request/
├── knw_10000012_v1.preview.presentation-request.json
└── knw_10000013_v1.preview.presentation-request.json
```

監査ログには判定条件と結果だけを保存し、Source Bundle全文やClaim本文は保存しません。
