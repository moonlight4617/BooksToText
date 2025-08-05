"""
進捗表示モジュール
リアルタイムの処理進捗表示とETA計算
"""

import time
import sys
from datetime import datetime, timedelta


class ProgressTracker:
    def __init__(self, total_items, logger=None):
        """
        進捗トラッカーの初期化
        
        Args:
            total_items: 総アイテム数
            logger: ログインスタンス
        """
        self.total_items = total_items
        self.current_item = 0
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.logger = logger
        
        # 処理速度計算用
        self.processing_times = []
        self.max_history = 10  # 最大10件の処理時間を保持
        
        # 進捗表示用
        self.bar_width = 50
        self.last_percentage = -1
        
        self.log_message(f"処理開始: 総ページ数 {total_items}")
    
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
    
    def update(self, current_item, item_name="", processing_time=None):
        """
        進捗を更新
        
        Args:
            current_item: 現在のアイテム番号
            item_name: アイテム名
            processing_time: 処理時間（秒）
        """
        self.current_item = current_item
        current_time = time.time()
        
        # 処理時間を記録
        if processing_time:
            self.processing_times.append(processing_time)
            if len(self.processing_times) > self.max_history:
                self.processing_times.pop(0)
        
        # 進捗率計算
        percentage = (current_item / self.total_items) * 100
        
        # 1%刻みまたは重要なタイミングで表示更新
        if (int(percentage) != self.last_percentage or 
            current_item % 5 == 0 or 
            current_item == self.total_items):
            
            self._display_progress(percentage, item_name)
            self.last_percentage = int(percentage)
        
        self.last_update_time = current_time
    
    def _display_progress(self, percentage, item_name=""):
        """
        進捗バーを表示
        
        Args:
            percentage: 進捗率
            item_name: 現在処理中のアイテム名
        """
        # 経過時間と推定残り時間
        elapsed_time = time.time() - self.start_time
        eta = self._calculate_eta(percentage, elapsed_time)
        
        # 平均処理速度
        avg_speed = self._calculate_average_speed()
        
        # プログレスバー作成
        filled_width = int(self.bar_width * percentage / 100)
        bar = '█' * filled_width + '░' * (self.bar_width - filled_width)
        
        # 時間フォーマット
        elapsed_str = self._format_time(elapsed_time)
        eta_str = self._format_time(eta) if eta else "計算中"
        
        # 進捗情報
        progress_info = (
            f"\r進捗: [{bar}] {percentage:.1f}% "
            f"({self.current_item}/{self.total_items}) "
            f"経過: {elapsed_str} ETA: {eta_str}"
        )
        
        if avg_speed:
            progress_info += f" 速度: {avg_speed:.1f}秒/ページ"
        
        if item_name:
            progress_info += f" | {item_name}"
        
        # コンソール表示（改行なし）
        sys.stdout.write(progress_info)
        sys.stdout.flush()
        
        # ログに記録（重要なタイミングのみ）
        if (self.current_item % 10 == 0 or 
            self.current_item == self.total_items or
            int(percentage) % 10 == 0):
            self.log_message(
                f"進捗 {percentage:.1f}% ({self.current_item}/{self.total_items}) "
                f"経過: {elapsed_str} ETA: {eta_str}"
            )
    
    def _calculate_eta(self, percentage, elapsed_time):
        """
        推定残り時間を計算
        
        Args:
            percentage: 現在の進捗率
            elapsed_time: 経過時間
            
        Returns:
            float: 推定残り時間（秒）
        """
        if percentage <= 0:
            return None
        
        # 複数の手法で推定
        estimates = []
        
        # 方法1: 全体の進捗率から推定
        if percentage > 5:  # 5%以上進んでから推定開始
            total_estimated_time = elapsed_time / (percentage / 100)
            remaining_time = total_estimated_time - elapsed_time
            estimates.append(remaining_time)
        
        # 方法2: 最近の処理速度から推定
        if self.processing_times:
            avg_time_per_item = sum(self.processing_times) / len(self.processing_times)
            remaining_items = self.total_items - self.current_item
            estimates.append(remaining_items * avg_time_per_item)
        
        # 方法3: 最近の処理ペースから推定
        if self.current_item > 1:
            items_per_second = self.current_item / elapsed_time
            remaining_items = self.total_items - self.current_item
            estimates.append(remaining_items / items_per_second)
        
        # 推定値の中央値を返す
        if estimates:
            estimates.sort()
            return estimates[len(estimates) // 2]
        
        return None
    
    def _calculate_average_speed(self):
        """
        平均処理速度を計算
        
        Returns:
            float: 平均処理時間（秒/アイテム）
        """
        if self.processing_times:
            return sum(self.processing_times) / len(self.processing_times)
        return None
    
    def _format_time(self, seconds):
        """
        秒数を読みやすい形式にフォーマット
        
        Args:
            seconds: 秒数
            
        Returns:
            str: フォーマット済み時間文字列
        """
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:.0f}分{seconds:.0f}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}時間{minutes:.0f}分"
    
    def add_error(self, error_message):
        """
        エラーを記録
        
        Args:
            error_message: エラーメッセージ
        """
        self.log_message(f"エラー: {error_message}", 'error')
    
    def complete(self):
        """
        処理完了時の表示
        """
        total_time = time.time() - self.start_time
        
        # 最終進捗バー表示
        self._display_progress(100.0, "完了")
        print()  # 改行
        
        # 完了サマリー
        avg_speed = self._calculate_average_speed()
        completion_msg = (
            f"\n処理完了! "
            f"総処理時間: {self._format_time(total_time)} "
            f"平均速度: {avg_speed:.1f}秒/ページ" if avg_speed else ""
        )
        
        self.log_message(completion_msg)
    
    def get_statistics(self):
        """
        処理統計を取得
        
        Returns:
            dict: 統計情報
        """
        elapsed_time = time.time() - self.start_time
        avg_speed = self._calculate_average_speed()
        
        return {
            'total_items': self.total_items,
            'completed_items': self.current_item,
            'completion_rate': (self.current_item / self.total_items) * 100,
            'elapsed_time': elapsed_time,
            'average_speed': avg_speed,
            'estimated_total_time': elapsed_time / (self.current_item / self.total_items) if self.current_item > 0 else None
        }