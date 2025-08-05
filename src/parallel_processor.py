"""
並列処理モジュール
複数のページを並列でOCR処理して高速化
"""

import multiprocessing as mp
import queue
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, TimeoutError

from ocr_processor import OCRProcessor
from utils import ImageUtils


class ParallelOCRProcessor:
    def __init__(self, logger=None, max_workers=None):
        """
        並列OCRプロセッサーの初期化
        
        Args:
            logger: ログインスタンス
            max_workers: 最大ワーカー数（None=自動設定）
        """
        self.logger = logger
        self.max_workers = max_workers or min(4, mp.cpu_count())  # 最大4プロセス
        self.results_queue = queue.Queue()
        self.error_count = 0
        
        self.log_message(f"並列処理初期化: 最大ワーカー数 {self.max_workers}")
    
    def log_message(self, message, level='info'):
        """ログ出力のヘルパー"""
        if self.logger:
            if level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
            else:
                self.logger.info(message)
        else:
            print(message)
    
    def process_images_parallel(self, image_files, progress_callback=None, killer=None):
        """
        画像ファイルを並列処理（キャンセル可能）
        
        Args:
            image_files: 処理する画像ファイルのリスト
            progress_callback: 進捗コールバック関数
            killer: GracefulKillerインスタンス（停止制御用）
            
        Returns:
            list: (index, extracted_text, confidence, processing_time) のタプルリスト
        """
        results = []
        
        try:
            # スレッドプール実行器を使用（プロセスプールよりメモリ効率が良い）
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 処理タスクをサブミット
                future_to_index = {}
                
                for i, image_path in enumerate(image_files):
                    # 開始前に停止チェック
                    if killer and killer.is_killed():
                        self.log_message("タスクサブミット中に停止要求を受信", 'warning')
                        break
                        
                    future = executor.submit(
                        self._process_single_image, 
                        image_path, 
                        i,
                        killer  # killerを渡す
                    )
                    future_to_index[future] = i
                
                if not future_to_index:
                    return []
                
                # 定期的な中断チェック付きで完了待機
                completed_count = 0
                remaining_futures = dict(future_to_index)
                
                while remaining_futures and not (killer and killer.is_killed()):
                    try:
                        # 短いタイムアウトで結果をチェック
                        done_futures = []
                        
                        for future in list(remaining_futures.keys()):
                            try:
                                result = future.result(timeout=0.5)  # 0.5秒タイムアウト
                                index = remaining_futures[future]
                                done_futures.append(future)
                                
                                if result:
                                    results.append(result)
                                    completed_count += 1
                                    
                                    # 進捗コールバック呼び出し
                                    if progress_callback:
                                        progress_callback(
                                            completed_count, 
                                            image_files[index].name,
                                            result[3]  # processing_time
                                        )
                                else:
                                    self.error_count += 1
                                    
                            except TimeoutError:
                                continue  # まだ完了していない
                            except Exception as e:
                                index = remaining_futures[future]
                                done_futures.append(future)
                                self.log_message(
                                    f"並列処理エラー (インデックス {index}): {e}", 
                                    'error'
                                )
                                self.error_count += 1
                        
                        # 完了したFutureを削除
                        for future in done_futures:
                            del remaining_futures[future]
                            
                    except KeyboardInterrupt:
                        if killer:
                            killer.kill_now.set()
                        break
                
                # グレースフルシャットダウン
                if killer and killer.is_killed():
                    self.log_message("並列処理の停止要求を処理中...", 'warning')
                    
                    # 未完了のタスクをキャンセル
                    cancelled_count = 0
                    for future in remaining_futures.keys():
                        if future.cancel():
                            cancelled_count += 1
                    
                    if cancelled_count > 0:
                        self.log_message(f"{cancelled_count}個のタスクをキャンセルしました", 'info')
                    
                    # Executorを即座にシャットダウン
                    try:
                        executor.shutdown(wait=False, cancel_futures=True)
                    except Exception as e:
                        self.log_message(f"Executor shutdown error: {e}", 'warning')
                    
                    self.log_message(
                        f"並列処理が中断されました。{completed_count}件処理完了、"
                        f"{len(remaining_futures)}件未完了", 'warning'
                    )
                    
                    # 中断の場合でも部分的な結果を返す
        
        except Exception as e:
            self.log_message(f"並列処理初期化エラー: {e}", 'error')
            return []
        
        # インデックス順にソート
        results.sort(key=lambda x: x[0])
        
        if killer and killer.is_killed():
            self.log_message(
                f"並列処理中断: {len(results)}件成功, {self.error_count}件エラー"
            )
        else:
            self.log_message(
                f"並列処理完了: {len(results)}件成功, {self.error_count}件エラー"
            )
        
        return results
    
    def _process_single_image(self, image_path, index, killer=None):
        """
        単一画像の処理（ワーカースレッド用、キャンセル可能）
        
        Args:
            image_path: 画像ファイルパス
            index: インデックス
            killer: GracefulKillerインスタンス
            
        Returns:
            tuple: (index, text, confidence, processing_time) または None
        """
        start_time = time.time()
        
        try:
            # 処理開始前に停止チェック
            if killer and killer.is_killed():
                return None
            
            # 各ワーカーで独立したインスタンスを作成
            image_utils = ImageUtils()
            ocr_processor = OCRProcessor()
            
            # 画像前処理（停止チェック付き）
            if killer and killer.is_killed():
                return None
                
            processed_image = image_utils.preprocess_image(image_path)
            if processed_image is None:
                self.log_message(f"画像前処理失敗: {image_path}", 'error')
                return None
            
            # OCR実行前に停止チェック
            if killer and killer.is_killed():
                return None
            
            # OCR実行
            text = ocr_processor.extract_text(processed_image)
            if not text.strip():
                self.log_message(f"テキスト抽出失敗: {image_path}", 'warning')
                return None
            
            # 最終チェック
            if killer and killer.is_killed():
                return None
            
            # 信頼度取得
            confidence = ocr_processor.get_confidence(processed_image)
            
            processing_time = time.time() - start_time
            
            return (index, text, confidence, processing_time)
            
        except Exception as e:
            # キャンセル例外の場合は静かに終了
            if killer and killer.is_killed():
                return None
                
            self.log_message(
                f"画像処理エラー {image_path}: {e}", 
                'error'
            )
            return None
    
    def process_images_batch(self, image_files, batch_size=4, progress_callback=None, killer=None):
        """
        バッチ処理による並列実行（キャンセル可能）
        
        Args:
            image_files: 処理する画像ファイルのリスト
            batch_size: バッチサイズ
            progress_callback: 進捗コールバック関数
            killer: GracefulKillerインスタンス
            
        Returns:
            list: 抽出されたテキストのリスト（順序保持）
        """
        all_results = []
        total_batches = (len(image_files) + batch_size - 1) // batch_size
        
        self.log_message(
            f"バッチ処理開始: {len(image_files)}ファイルを"
            f"{total_batches}バッチで処理"
        )
        
        for batch_index in range(total_batches):
            # バッチ開始前に停止チェック
            if killer and killer.is_killed():
                self.log_message(
                    f"バッチ処理が中断されました (バッチ {batch_index + 1}/{total_batches})"
                )
                break
                
            start_idx = batch_index * batch_size
            end_idx = min(start_idx + batch_size, len(image_files))
            batch_files = image_files[start_idx:end_idx]
            
            self.log_message(
                f"バッチ {batch_index + 1}/{total_batches}: "
                f"{len(batch_files)}ファイル処理中"
            )
            
            # バッチを並列処理
            batch_results = self.process_images_parallel(
                batch_files, 
                progress_callback,
                killer
            )
            
            # 結果をインデックス調整して追加
            for index, text, confidence, proc_time in batch_results:
                adjusted_index = start_idx + index
                all_results.append((adjusted_index, text, confidence, proc_time))
            
            # バッチ完了後に停止チェック
            if killer and killer.is_killed():
                self.log_message(
                    f"バッチ処理が中断されました (完了: {batch_index + 1}/{total_batches})"
                )
                break
        
        # 最終的にインデックス順でソート
        all_results.sort(key=lambda x: x[0])
        
        return all_results


class AdaptiveProcessor:
    """
    システムリソースに応じて処理方法を自動調整するプロセッサー
    """
    
    def __init__(self, logger=None):
        self.logger = logger
        self.system_info = self._get_system_info()
        self.processing_mode = self._determine_optimal_mode()
    
    def _get_system_info(self):
        """システム情報を取得"""
        import psutil
        
        info = {
            'cpu_count': mp.cpu_count(),
            'memory_gb': psutil.virtual_memory().total / (1024**3),
            'available_memory_gb': psutil.virtual_memory().available / (1024**3)
        }
        
        if self.logger:
            self.logger.info(
                f"システム情報: CPU {info['cpu_count']}コア, "
                f"メモリ {info['memory_gb']:.1f}GB "
                f"(利用可能: {info['available_memory_gb']:.1f}GB)"
            )
        
        return info
    
    def _determine_optimal_mode(self):
        """最適な処理モードを決定"""
        cpu_count = self.system_info['cpu_count']
        available_memory = self.system_info['available_memory_gb']
        
        if cpu_count >= 4 and available_memory >= 4:
            mode = "high_parallel"
            workers = min(4, cpu_count)
        elif cpu_count >= 2 and available_memory >= 2:
            mode = "medium_parallel" 
            workers = 2
        else:
            mode = "sequential"
            workers = 1
        
        if self.logger:
            self.logger.info(f"処理モード: {mode} (ワーカー数: {workers})")
        
        return {"mode": mode, "workers": workers}
    
    def get_recommended_settings(self):
        """推奨設定を取得"""
        return {
            'max_workers': self.processing_mode['workers'],
            'batch_size': min(8, self.processing_mode['workers'] * 2),
            'use_parallel': self.processing_mode['workers'] > 1
        }