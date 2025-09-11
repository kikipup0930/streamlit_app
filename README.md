# 📝 手書きOCR + GPT要約アプリ（Streamlit + Azure）

## 📌 概要
このアプリは、アップロードした手書き画像から文字を読み取り（OCR）、GPT-3.5で自動要約を行うStreamlitアプリです。
処理結果はAzure Blob Storageに自動で保存されます。

## ⚙ 使用技術
- Python 3.x
- Streamlit
- easyocr（日本語OCR）
- OpenAI GPT（要約）
- Azure Blob Storage（クラウド保存）
- Azure App Service（Web公開）

## 🔧 インストール手順（ローカル環境）
```bash
pip install -r requirements.txt
```

## 🚀 起動方法（ローカル）
```bash
streamlit run app.py
```

## ☁ Azure App Service デプロイ手順
```bash
az login
az webapp up --name YOUR_APP_NAME --resource-group YOUR_RESOURCE_GROUP --runtime "PYTHON|3.10"
```

## 🔐 `.streamlit/secrets.toml` 設定（ローカル用）
```toml
OPENAI_API_KEY = "your-openai-api-key"
AZURE_STORAGE_CONNECTION_STRING = "your-azure-blob-connection-string"
```
※ Azure にデプロイする際は、これらのキーを App Service のアプリ設定に追加してください。

## 📁 ディレクトリ構成
```plaintext
streamlit_app/
├── app.py
├── utils.py
├── requirements.txt
├── startup.txt
├── README.md
└── .streamlit/
    └── secrets.toml
```

## ⚠ 注意点
- `.streamlit/secrets.toml` は **絶対に公開しない** でください（GitHub除外推奨）
- Azure接続文字列・APIキーの流出に注意

---

## 📅 進捗メモ（2025年7月10日）

### ✅ 本日の成果

- **Azure OCRによる画像認識処理を安定化**
  - `readResult.pages` 構造と `readResult.content` 構造の両方に対応
  - 印刷文字の精度を高めるために前処理（グレースケール・コントラスト補正）を実装

- **GPTによる要約処理を導入**
  - OpenAI GPT-4を使った日本語要約機能を組み込み
  - 長文OCR結果に対しても安定して動作することを確認

- **CSV保存形式を「追記型」に改修**
  - これまで毎回新規ファイルとして保存していたログを、1つの `ocr_result.csv` に追記する方式に変更
  - Azure Blob Storage上で1ファイルで管理可能になり、今後の可視化や分析が容易に

- **保存処理の自動化とエラー回避策**
  - ファイル名長すぎによる Azure エラー（OutOfRangeInput）を回避する設計に変更
  - コンテナが存在しない場合に自動作成されるように処理を追加

### 🧩 課題と対応

- `pages` 構造が存在しないOCRレスポンスに対応する必要があり、レスポンス形式に柔軟に対応できるよう `run_ocr()` 関数を改修
- ファイル名の長さ制限に起因するBlob保存失敗を検出し、解決策としてファイル名のハッシュ化・短縮を検討（今後導入予定）

### 💡 今後の展望

- Streamlitアプリ上で **CSVの履歴を一覧表示** するUIを追加することで利便性を高めたい
- 一つのcsvに追記方式になっていなかったので、追記方式にする(保存ボタンでエラー発生)

### ✅ 本日の成果(7/17)

- **ノートの写真追加**
  - ノートの写真を名前を整理し追加した
- **secretの中身を統一**
  - AZURE_ENDPOINT
  - AZURE_KEY
  - AZURE_CONTAINER
  - AZURE_CONNECTION_STRING
  - OPENAI_API_KEY 

- **azure openAIをgpt3.5に変更**
  - デプロイ名 → gpt-35-turbo
 - **csv保存を追記式に変更**
  - ocr_resultsに追記


### 🧩 課題と対応
- csvが文字化けしているので直す

### 💡 今後の展望

### ✅ 本日の成果 (9/4)

- **履歴一覧タブを実装**
  - 保存された `ocr_result.csv` をBlobから読み込み
  - DataFrameとして一覧表示
  - キーワード検索・日付フィルタが可能
  - フィルタ結果をCSVダウンロードできるようにした
  - OCR件数の推移をグラフ化


### 🧩 課題と対応
- **CSVの文字化け**
  - Googleドライブでは問題なく読めることを確認
  - Excelでの化けは発生するが、今回はUTF-8のまま運用で問題なしと判断
- **依存関数不足によるエラー**
  - `app.py` と `utils.py` の関数を統一し、ImportErrorを解消


### 💡 今後の展望
- **履歴の操作性強化**
  - クリックで詳細表示（OCR全文や要約を大きく表示）
  - 特定行の削除・編集機能
- **UI強化**

### ✅ 本日の成果 (9/4)



### 🧩 課題と対応



### 💡 今後の展望
