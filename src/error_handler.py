"""
エラーハンドリングモジュール
高度なエラー処理とリトライ機能
"""

import time
import traceback
from functools import wraps
from pathlib import Path
import json
import os


class OCRError(Exception):
    """OCR処理専用例外クラス"""
    pass


class FileProcessError(Exception):
    """ファイル処理専用例外クラス"""
    pass


class ErrorHandler:
    def __init__(self, logger, max_retries=3, retry_delay=1.0):
        """
        エラーハンドラーの初期化
        
        Args:
            logger: ログインスタンス
            max_retries: 最大リトライ回数
            retry_delay: リトライ間隔（秒）
        """
        self.logger = logger
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.error_stats = {
            'total_errors': 0,
            'ocr_errors': 0,
            'file_errors': 0,
            'unknown_errors': 0,
            'recovered_errors': 0
        }
    
    def validate_input_directory(self, input_dir):
        """
        入力ディレクトリの詳細検証
        
        Args:
            input_dir: 入力ディレクトリパス
            
        Raises:
            FileProcessError: ディレクトリ問題がある場合
        """
        input_path = Path(input_dir)
        
        if not input_path.exists():
            raise FileProcessError(f"入力ディレクトリが存在しません: {input_dir}")
        
        if not input_path.is_dir():
            raise FileProcessError(f"指定されたパスはディレクトリではありません: {input_dir}")
        
        # 読み取り権限確認
        if not os.access(input_path, os.R_OK):
            raise FileProcessError(f"ディレクトリの読み取り権限がありません: {input_dir}")
        
        # 画像ファイルの存在確認
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        image_files = [f for f in input_path.iterdir() 
                      if f.is_file() and f.suffix.lower() in image_extensions]
        
        if not image_files:
            raise FileProcessError(f"画像ファイルが見つかりません: {input_dir}")
        
        self.logger.info(f"入力ディレクトリ検証完了: {len(image_files)}個の画像ファイルを検出")
        return image_files
    
    def validate_output_directory(self, output_dir):
        """
        出力ディレクトリの検証と作成
        
        Args:
            output_dir: 出力ディレクトリパス
        """
        output_path = Path(output_dir)
        
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 書き込み権限確認
            if not os.access(output_path, os.W_OK):
                raise FileProcessError(f"出力ディレクトリの書き込み権限がありません: {output_dir}")
            
            self.logger.info(f"出力ディレクトリ確認完了: {output_dir}")
            
        except OSError as e:
            raise FileProcessError(f"出力ディレクトリの作成に失敗: {output_dir} - {e}")
    
    def validate_image_file(self, image_path):
        """
        画像ファイルの詳細検証
        
        Args:
            image_path: 画像ファイルパス
            
        Returns:
            bool: 検証結果
        """
        try:
            from PIL import Image
            
            # ファイルサイズ確認
            file_size = image_path.stat().st_size
            if file_size == 0:
                self.logger.warning(f"空のファイル: {image_path}")
                return False
            
            if file_size > 50 * 1024 * 1024:  # 50MB以上
                self.logger.warning(f"ファイルサイズが大きすぎます: {image_path} ({file_size / 1024 / 1024:.1f}MB)")
            
            # 画像として開けるか確認
            with Image.open(image_path) as img:
                width, height = img.size
                if width < 100 or height < 100:
                    self.logger.warning(f"画像サイズが小さすぎます: {image_path} ({width}x{height})")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"画像ファイル検証エラー: {image_path} - {e}")
            return False
    
    def retry_on_failure(self, operation_name="操作"):
        """
        失敗時リトライデコレーター
        
        Args:
            operation_name: 操作名
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        result = func(*args, **kwargs)
                        
                        # 成功時
                        if attempt > 0:
                            self.logger.info(f"{operation_name}が{attempt + 1}回目で成功")
                            self.error_stats['recovered_errors'] += 1
                        
                        return result
                        
                    except Exception as e:
                        last_exception = e
                        self.error_stats['total_errors'] += 1
                        
                        if isinstance(e, OCRError):
                            self.error_stats['ocr_errors'] += 1
                        elif isinstance(e, FileProcessError):
                            self.error_stats['file_errors'] += 1
                        else:
                            self.error_stats['unknown_errors'] += 1
                        
                        if attempt < self.max_retries:
                            self.logger.log_retry_attempt(attempt + 1, self.max_retries, operation_name)
                            self.logger.error(f"エラー詳細: {e}")
                            time.sleep(self.retry_delay * (attempt + 1))  # 指数バックオフ
                        else:
                            self.logger.error(f"{operation_name}が最大リトライ回数に達しました")
                
                # 最終的に失敗
                context = {
                    '操作': operation_name,
                    'リトライ回数': self.max_retries,
                    '最終エラー': str(last_exception),
                    'スタックトレース': traceback.format_exc()
                }
                self.logger.log_error_with_context(last_exception, context)
                
                raise last_exception
            
            return wrapper
        return decorator
    
    def safe_file_operation(self, operation_func, file_path, operation_name):
        """
        安全なファイル操作
        
        Args:
            operation_func: 実行する関数
            file_path: ファイルパス
            operation_name: 操作名
            
        Returns:
            実行結果（成功時）またはNone（失敗時）
        """
        try:
            result = operation_func(file_path)
            self.logger.debug(f"{operation_name}成功: {file_path}")
            return result
        except FileNotFoundError:
            self.logger.error(f"ファイルが見つかりません ({operation_name}): {file_path}")
        except PermissionError:
            self.logger.error(f"ファイルアクセス権限がありません ({operation_name}): {file_path}")
        except OSError as e:
            self.logger.error(f"ファイルシステムエラー ({operation_name}): {file_path} - {e}")
        except Exception as e:
            import traceback
            self.logger.error(f"予期しないエラー ({operation_name}): {file_path} - {e}")
            self.logger.error(f"詳細トレースバック: {traceback.format_exc()}")
        
        return None
    
    def create_progress_checkpoint(self, checkpoint_file, processed_files, current_index):
        """
        進捗チェックポイントの作成
        
        Args:
            checkpoint_file: チェックポイントファイルパス
            processed_files: 処理済みファイルリスト
            current_index: 現在のインデックス
        """
        try:
            checkpoint_data = {
                'processed_files': [str(f) for f in processed_files],
                'current_index': current_index,
                'timestamp': time.time()
            }
            
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"チェックポイント作成: {checkpoint_file}")
            
        except Exception as e:
            self.logger.warning(f"チェックポイント作成失敗: {e}")
    
    def load_progress_checkpoint(self, checkpoint_file):
        """
        進捗チェックポイントの読み込み
        
        Args:
            checkpoint_file: チェックポイントファイルパス
            
        Returns:
            dict: チェックポイントデータ（存在しない場合はNone）
        """
        try:
            if Path(checkpoint_file).exists():
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.logger.info(f"チェックポイント読み込み: {len(data.get('processed_files', []))}ファイル処理済み")
                return data
            
        except Exception as e:
            self.logger.warning(f"チェックポイント読み込み失敗: {e}")
        
        return None
    
    def get_error_statistics(self):
        """エラー統計情報を取得"""
        return self.error_stats.copy()
    
    def log_final_statistics(self):
        """最終統計情報をログ出力"""
        stats = self.error_stats
        self.logger.info("=== エラー統計情報 ===")
        self.logger.info(f"総エラー数: {stats['total_errors']}")
        self.logger.info(f"OCRエラー: {stats['ocr_errors']}")
        self.logger.info(f"ファイルエラー: {stats['file_errors']}")
        self.logger.info(f"不明エラー: {stats['unknown_errors']}")
        self.logger.info(f"復旧成功: {stats['recovered_errors']}")
        
        if stats['total_errors'] > 0:
            recovery_rate = (stats['recovered_errors'] / stats['total_errors']) * 100
            self.logger.info(f"復旧率: {recovery_rate:.1f}%")