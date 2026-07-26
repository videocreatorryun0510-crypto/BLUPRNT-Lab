# Phase 5.3 — Specimen & Relation Resolution

## 目的

`specimen`を正式Knowledge Categoryとして登録し、未解決Relationが既存IDを維持したまま正式Knowledgeへ解決される流れを実証します。

```text
塗抹標本をWorkbenchから保存
        ↓
Knowledge Schema / Specimen Completeness
        ↓
Knowledge Registry（knw_10000005）
        ↓
保存済みstaining_methodだけを再評価
        ↓
Gram染色 uses_specimen
unresolved_relation → resolved
```

Gram染色Knowledge JSONは更新しません。変更されるのは独立Relation台帳だけです。

## Specimen Category Contract

`specimen_v1.0`は次を保持します。

- `specimen_kind`：血清、血漿、全血、尿、便、喀痰、髄液、塗抹標本、その他
- `overview`：検体・標本の概要
- `uses`：使用用途
- `collection_methods`：採取元、採取・作製方法、容器・器具
- `storage_conditions`：温度、時間、条件
- `cautions`：品質・安全・解釈上の注意

定義、概要、使用用途、採取・作製方法、保存条件、注意事項を85点、出典を15点としてCompletenessを評価します。採取・作製方法または保存条件が欠けた場合は49点以下です。

## Relation Resolution

Resolverは最初にRegistryの正式名称とaliasを完全一致で確認します。`uses_specimen`に限り、登録済みSpecimenの正式名称が元文字列の末尾に一意に現れる場合も解決できます。

```text
元文字列：細菌を含む塗抹標本
正式Knowledge：塗抹標本（knw_10000005）
Context：細菌を含む
Preparation：薄く均一に塗抹する。
```

この規則は登録済みSpecimenだけを対象とし、AI・類似度・医学的推測を使いません。候補が複数なら未解決のままです。

## Relation Context

Relation Version 1.1では次を追加しました。

```json
{
  "context": {
    "qualifiers": ["細菌を含む"],
    "preparation": "薄く均一に塗抹する。"
  }
}
```

「塗抹標本」の普遍的な定義へ「細菌を含む」を混ぜると、血液塗抹標本や病理標本へ再利用できなくなります。そのため利用条件はRelation側へ保存します。

## 実装結果

| 指標 | Phase 5.2 | Phase 5.3 |
|---|---:|---:|
| Relation総数 | 7 | 7 |
| Resolved | 0 | 1 |
| Unresolved | 7 | 6 |
| Resolution率 | 0% | 14.3% |
| Gram染色Knowledge Version | v1 | v1 |
| uses_specimen Relation Version | v1 | v2 |

## 運用

1. Workbenchで「塗抹標本を開く」を押す
2. JSON、出典、Completenessを確認する
3. 操作者と変更理由を確認し「Registryへ保存」を押す
4. RegistryでGram染色を開く
5. 「関連Knowledge」で塗抹標本、`knw_10000005`、`resolved`、Contextを確認する

登録済みSpecimenを変更しても、Gram染色本文は更新しません。Relationの接続条件が変わる場合だけRelation Versionと履歴が増えます。
