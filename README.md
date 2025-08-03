# Kindle to Text Converter

Kindle書籍のスクリーンショット画像を自動でOCR解析し、テキスト情報に変換する自動化ワークフロー

## 技術選定

### OCRエンジン
- **Tesseract OCR**: 無料・オープンソースのOCRエンジン
- 日本語対応（jpn言語パック使用）

### プログラミング言語・ライブラリ
- **Python 3.8+**
- **pytesseract**: TesseractのPythonラッパー
- **Pillow (PIL)**: 画像処理ライブラリ
- **OpenCV**: 画像前処理用（必要に応じて）

## ディレクトリ構造

```
kindleToText/
├── input/               # Kindleスクリーンショット画像
│   └── book_name/       # 書籍ごとにフォルダ分け
│       ├── page_001.png
│       ├── page_002.png
│       └── ...
├── output/              # 抽出されたテキスト
│   └── book_name.txt    # 書籍名のテキストファイル
├── src/                 # Pythonスクリプト
│   ├── main.py          # メインスクリプト
│   ├── ocr_processor.py # OCR処理
│   └── utils.py         # ユーティリティ関数
├── temp/                # 中間処理ファイル（必要時）
└── requirements.txt     # Pythonライブラリ
```

## データフロー

1. **入力準備**: `input/book_name/` にスクリーンショット画像を配置
2. **画像読み込み**: ファイル名順で画像を順次読み込み  
3. **前処理**: 必要に応じて画像のコントラスト調整
4. **OCR処理**: Tesseractでテキスト抽出
5. **後処理**: 改行調整、ノイズ除去
6. **出力**: `output/book_name.txt` に全ページのテキストを結合

## セットアップ

### 1. 仮想環境の構築

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 仮想環境の無効化（作業終了時）
deactivate
```

### 2. Tesseract OCRのインストール

**Windows:**
```bash
# Chocolateyを使用
choco install tesseract

# または公式サイトからダウンロード
# https://github.com/UB-Mannheim/tesseract/wiki
```

**macOS:**
```bash
brew install tesseract
brew install tesseract-lang
```

**Linux (Ubuntu):**
```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-jpn
```

### 3. Pythonライブラリのインストール

```bash
# 仮想環境を有効化してからインストール
pip install -r requirements.txt
```

## 使用方法

1. 仮想環境を有効化
```bash
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```
2. Kindleスクリーンショットを `input/book_name/` に配置
3. OCR処理を実行
```bash
python src/main.py --book book_name
```
4. `output/book_name.txt` から結果を確認

## 成功基準

- 300-500ページの技術書を2-3時間以内で処理完了
- OCR精度：90%以上の文字認識率
- 後工程でAIツールが活用可能なテキスト品質