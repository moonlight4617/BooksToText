"""
ログ機能モジュール
処理状況の記録とエラートラッキング
"""

import logging
import os
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_dir="logs", log_level=logging.INFO):
        """
        ログ機能の初期化
        
        Args:
            log_dir: ログファイル保存ディレクトリ
            log_level: ログレベル
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # ログファイル名（日時付き）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"kindle_ocr_{timestamp}.log"
        
        # ロガーの設定
        self.logger = logging.getLogger("KindleOCR")
        self.logger.setLevel(log_level)
        
        # ハンドラーが既に存在する場合は削除（重複防止）
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # ファイルハンドラー
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        
        # コンソールハンドラー
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        
        # フォーマッター
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # ハンドラーを追加
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message):
        """情報レベルログ"""
        self.logger.info(message)
    
    def warning(self, message):
        """警告レベルログ"""
        self.logger.warning(message)
    
    def error(self, message):
        """エラーレベルログ"""
        self.logger.error(message)
    
    def debug(self, message):
        """デバッグレベルログ"""
        self.logger.debug(message)
    
    def critical(self, message):
        """クリティカルレベルログ"""
        self.logger.critical(message)
    
    def log_processing_start(self, book_name, total_pages):
        """処理開始ログ"""
        self.info(f"処理開始: {book_name} (総ページ数: {total_pages})")
    
    def log_processing_end(self, book_name, total_time, success_count, error_count):
        """処理終了ログ"""
        self.info(f"処理完了: {book_name}")
        self.info(f"処理時間: {total_time:.2f}秒")
        self.info(f"成功ページ: {success_count}, エラーページ: {error_count}")
    
    def log_page_processing(self, page_num, total_pages, filename, ocr_confidence=None):
        """ページ処理ログ"""
        if ocr_confidence:
            self.info(f"ページ {page_num}/{total_pages}: {filename} (信頼度: {ocr_confidence:.1f}%)")
        else:
            self.info(f"ページ {page_num}/{total_pages}: {filename}")
    
    def log_error_with_context(self, error, context_info):
        """コンテキスト付きエラーログ"""
        self.error(f"エラー発生: {error}")
        for key, value in context_info.items():
            self.error(f"  {key}: {value}")
    
    def log_retry_attempt(self, attempt, max_attempts, operation):
        """リトライ試行ログ"""
        self.warning(f"リトライ {attempt}/{max_attempts}: {operation}")
    
    def get_log_file_path(self):
        """ログファイルパスを取得"""
        return str(self.log_file)