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

### 方法1: 一括処理（推奨）

**最も簡単な方法：**
```bash
# 仮想環境を有効化
venv\Scripts\activate

# 完全自動処理（スクリーンショット + OCR）
python kindle_full_process.py --book "技術書名"

# 高速処理（並列OCR）
python kindle_full_process.py --book "技術書名" --parallel

# ページ範囲指定
python kindle_full_process.py --book "技術書名" --start 1 --end 100 --parallel

# 高品質設定（推奨）
python kindle_full_process.py --book "技術書名" --delay 2.5 --parallel
```

**実行例:**
```bash
# 実際の書籍での実行例
python kindle_full_process.py --book "ブラウザのしくみ" --start 1 --end 50 --delay 2.0 --parallel

# 処理時間の目安:
# - 50ページ: 約3-5分（スクリーンショット2分 + OCR1-3分）
# - 200ページ: 約15-25分
# - 500ページ: 約40-70分
```

### 方法2: 段階的処理

1. 仮想環境を有効化
```bash
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

2. Kindleアプリで書籍を開く
   - Windows版Kindleアプリを起動
   - 対象書籍を開いて開始ページを表示

3. 自動スクリーンショット実行
```bash
# 基本使用（手動停止まで）
python kindle_capture.py --book "書籍名"

# ページ範囲指定
python kindle_capture.py --book "書籍名" --start 1 --end 100

# カスタム設定
python kindle_capture.py --book "書籍名" --delay 3.0 --key space
```

4. OCR処理を実行
```bash
# 基本実行
python src/main.py --book "書籍名"

# 並列処理で高速化
python src/main.py --book "書籍名" --parallel

# デバッグレベルで詳細ログ
python src/main.py --book "書籍名" --log-level DEBUG
```

5. `output/book_name.txt` から結果を確認

### 方法2: 手動スクリーンショット + OCR処理

1. 仮想環境を有効化
2. Kindleスクリーンショットを手動で `input/book_name/` に配置
3. OCR処理を実行
```bash
python src/main.py --book book_name
```
4. `output/book_name.txt` から結果を確認

## OCR精度向上機能

### 高度な画像前処理
- **解像度アップスケーリング**: 画像を2倍に拡大してOCR精度を向上
- **ノイズ除去**: Non-local Means Denoisingによる高品質なノイズ除去
- **コントラスト強化**: CLAHE（適応ヒストグラム平均化）による文字の鮮明化
- **傾き補正**: Hough変換による自動傾き検出・補正
- **モルフォロジー処理**: 文字の形状を最適化
- **適応的二値化**: Otsuの手法による最適な二値化
- **小ノイズ除去**: 連結成分分析による微細ノイズの除去

### OCR処理の最適化
- **複数PSM設定**: 5種類のページセグメンテーションモードで並行処理
- **信頼度ベース選択**: 最も信頼度の高い結果を自動選択
- **文字領域検出**: MSER（Maximally Stable Extremal Regions）による文字領域の特定
- **エラー耐性**: 複数の処理方法でフォールバック機能

### 処理時間とのトレードオフ
- **精度重視モード**: 高品質な結果を得るため処理時間が増加（2-3倍）
- **従来比**: OCR精度が大幅向上（誤認識文字の減少、文字構造の改善）

## 自動スクリーンショット機能

### 対応環境
- **OS**: Windows 10/11
- **アプリ**: Windows版Kindleアプリ
- **Python**: 3.8以上
- **モニター**: シングル・マルチモニター両対応

### 機能概要
- **Win32 API直接キャプチャ**: マルチモニター環境完全対応
- **インテリジェントウィンドウ検出**: 実際のKindle for PCアプリを自動識別
- **ページ自動めくり**: キーボード操作によるページ送り
- **高品質キャプチャ**: UIフレームを除いたコンテンツ領域のみ抽出
- **PNG形式保存**: OCR処理に最適化された画像形式

### 安全機能
- **緊急停止**: マウスを画面左上角に移動
- **通常停止**: Ctrl+C
- **事前確認**: 実行前の準備状況確認

## 緊急停止方法

OCR処理が停止できない場合の対処法：

### Windows
```bash
# 全てのPythonプロセスを強制終了
taskkill /f /im python.exe

# 特定のプロセスIDで終了（推奨）
# 1. プロセスIDを確認
tasklist /fi "imagename eq python.exe"
# 2. 該当するプロセスIDを指定して終了
taskkill /f /pid <プロセスID>
```

### macOS/Linux
```bash
# プロセス一覧から該当プロセスを確認
ps aux | grep python

# プロセスIDを指定して終了（推奨）
kill -9 <プロセスID>

# 全てのPythonプロセスを強制終了（注意）
pkill -f python
```

### タスクマネージャー（Windows GUI）
1. `Ctrl + Shift + Esc` でタスクマネージャーを開く
2. 「詳細」タブで `python.exe` を検索
3. 該当プロセスを右クリック → 「タスクの終了」

### 停止困難な原因
- **並列処理**: 複数スレッドで同時実行中
- **重いOCR処理**: 画像解析処理の途中
- **サブプロセス実行**: 子プロセスへのシグナル未伝達

### 予防策
- 小さなページ範囲でテスト実行
- `--workers 2` で並列度を下げる
- 処理開始前にタスクマネージャーでプロセス確認

### カスタマイズ可能な設定
- **ページ範囲**: 開始・終了ページ指定
- **待機時間**: ページめくり後の待機時間調整
- **操作キー**: right/space/pagedownキー選択
- **出力先**: 保存ディレクトリのカスタマイズ

### 注意事項と推奨設定

#### 推奨環境設定
1. **Kindleアプリの配置**:
   - メインモニターでの使用を推奨（マルチモニター環境でも動作可能）
   - ウィンドウサイズ: 最小800x600以上（フルスクリーンでなくても可）
   - 推奨サイズ: 1200x800以上（OCR精度向上のため）

2. **Kindleアプリの設定**:
   - フォントサイズ: 中〜大（小さすぎるとOCR精度低下）
   - 背景色: 白背景推奨（セピアや黒背景は避ける）
   - 余白: デフォルト設定で十分

3. **システム設定**:
   - ディスプレイ倍率: 100%推奨（125%、150%でも動作可能）
   - スクリーンセーバー: 処理中は無効化推奨

#### 使用上の注意事項
1. **事前準備**:
   - Kindleアプリを事前に起動し、対象書籍を開いてください
   - 開始ページを表示した状態でスクリプト実行
   - 他のアプリケーションを最小化して誤動作を防止

2. **パフォーマンス調整**:
   - ページ読み込み速度に応じて `--delay` を調整（1.5〜3.0秒）
   - 高速なSSDの場合: `--delay 1.5`
   - 通常のHDD: `--delay 2.5`以上
   
3. **長時間処理の対策**:
   - 大量ページ処理時はスクリーンセーバーを無効化
   - 電源設定で「画面をオフにしない」設定を推奨
   - Windows Updateの自動再起動を一時無効化

#### トラブルシューティング
- **スクリーンショットが黒い**: Kindleウィンドウがアクティブか確認
- **文字認識精度が低い**: フォントサイズを大きくする
- **処理が途中で止まる**: `--delay` を長めに設定

## 成功基準

- **自動化**: Kindleスクリーンショット → OCR処理の完全自動化
- **処理時間**: 300-500ページを4-6時間以内で完全処理（スクリーンショット + OCR）
- **OCR精度**: 95%以上の文字認識率
- **使いやすさ**: コマンド一発での実行可能