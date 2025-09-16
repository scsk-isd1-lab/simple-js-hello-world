# Simple JavaScript Hello World

シンプルなJavaScript Hello Worldアプリケーション

## 概要

このプロジェクトは、基本的なHTMLとJavaScriptを使ってHello Worldを表示するシンプルなウェブアプリケーションです。

## 機能

- HTMLページで"Hello World"ヘッダーを表示
- JavaScriptでコンソールに"Hello, World!"を出力

## 使い方

1. リポジトリをクローンまたはダウンロード
2. `index.html`をブラウザで開く
3. Hello Worldが表示され、コンソールにログが出力

## 開発 / テスト

- 単体テスト: `npm test`
- カバレッジ付き: `npm run test:coverage`
- GitHub Actions ワークフローの dry-run: `npm run act:dry-run`
- `act` での `/apply` ジョブ検証: `.env.test` を参照して `npm run act:test`

`.env.test` には `ACT_PR_*` や `ACT_PROMPT_TEXT`、`ACT_GITHUB_TOKEN` など `act` 実行時に必要なモック値が定義されています。GitHub Script やプロンプト生成ステップはこれらを使ってダミー値を出力するため、実トークンなしでも dry-run／テストが可能です。

## ライセンス

このプロジェクトは[LICENSE](LICENSE)ファイルで指定されたライセンスの下で公開されています。
