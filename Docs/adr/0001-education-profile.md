# ADR 0001: Education ProfileをKnowledgeと表示Profileの間に置く

- 状態: Accepted
- 日付: 2026-07-17
- 対象: Phase 3.2

## 背景

Content Profileは掲載候補、Visual Profileは図解候補、LayoutとThemeは表示方法を決めます。しかし、学習者へ何を先に教え、どこまで深く扱い、国家試験情報をどう強調するかを管理する場所がありませんでした。

## 採用した設計

Education ProfileをPublisher Coreの独立した版付きProfileとして追加し、`Content → Education → Visual → Layout → Theme`の順でPublication Planを作ります。

- Knowledge JSON、Exam Metadata、Registryは読み取り専用
- Education Profileは学習目的、難易度、順序、強調、比較・Visual優先を保持
- 教育用の完成文章や語呂合わせ本文は保持しない
- Templateは標準Education Profileを参照できる
- Publication RequestはEducation Profileだけを別Versionへ差し替えられる
- Publication Plan 1.1が解決済みの教育指示を保持する
- Publication Plan 1.0は後方互換として残す

## 採用しなかった設計

### Knowledge JSONへ教育順を保存する

同じ医学的事実を国家試験、臨床、新人、SNSで再利用できなくなるため採用しません。

### Content Profileへ教育ルールを追加する

「何を掲載するか」と「どう教えるか」が混ざり、Profileの組合せを変更しにくくなるため採用しません。

### Layout Profileだけで順序を表す

配置順と理解の順序は異なり、動画・note・問題へ再利用できないため採用しません。

### AIに毎回、教育順を自由判断させる

再現性、シリーズ統一、レビュー可能性が失われるため採用しません。

## 結果

同じKnowledge SourceとContent候補を保ったまま、Education Profileだけで学習順、深さ、試験強調、Visual優先を切り替えられます。新しい用途は新Profile Versionとして追加でき、過去教材の再現性も保てます。

## 将来変更する可能性

- 学習者属性や利用実績に基づく適応型Education Profile
- 学習目標標準やコンピテンシーとの対応
- Instagram、Reels等を明示するOutput KindまたはMedia Profile
- 教育ブロック本文の生成・承認・版管理
- Profile編集画面と承認ワークフロー
