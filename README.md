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

以上が `README.md` の提出用テンプレートです。
プロジェクトのトップディレクトリに保存して活用してください。