"""
シグナルハンドラーモジュール
Ctrl+CやSIGTERMによるグレースフル停止処理
"""

import signal
import sys
import threading
import time
import os


class GracefulKiller:
    """
    グレースフル停止処理を管理するクラス
    全スレッドで共有される停止フラグを提供
    """
    
    def __init__(self, logger=None):
        """
        初期化
        
        Args:
            logger: ログインスタンス
        """
        self.kill_now = threading.Event()  # 全スレッド共有の停止フラグ
        self.logger = logger
        self.shutdown_initiated = False
        self.start_time = time.time()
        
        # SIGINTとSIGTERMをハンドル
        signal.signal(signal.SIGINT, self._exit_gracefully)
        if os.name != 'nt':  # Unix系のみSIGTERMを設定
            signal.signal(signal.SIGTERM, self._exit_gracefully)
        
        if self.logger:
            self.logger.debug("シグナルハンドラーを初期化しました")
    
    def _exit_gracefully(self, signum, frame):
        """
        シグナル受信時のハンドラー
        
        Args:
            signum: シグナル番号
            frame: フレームオブジェクト
        """
        if not self.shutdown_initiated:
            self.shutdown_initiated = True
            signal_name = "SIGINT" if signum == signal.SIGINT else f"Signal {signum}"
            
            if self.logger:
                self.logger.warning(f"{signal_name}を受信しました。処理を停止します...")
                self.logger.info("進行中のタスクの完了を待機しています（最大10秒）")
            else:
                print(f"\n{signal_name}を受信しました。処理を停止します...")
                print("進行中のタスクの完了を待機しています（最大10秒）")
            
            # 全ワーカーに停止シグナル送信
            self.kill_now.set()
            
            # 10秒後に強制終了
            threading.Timer(10.0, self._force_exit).start()
        else:
            # 2回目のシグナルで即座に強制終了
            if self.logger:
                self.logger.error("2回目の停止要求を受信しました。強制終了します")
            else:
                print("\n強制終了します...")
            self._force_exit()
    
    def _force_exit(self):
        """強制終了処理"""
        if self.logger:
            elapsed_time = time.time() - self.start_time
            self.logger.error(f"タイムアウトまたは強制終了要求 (実行時間: {elapsed_time:.1f}秒)")
        
        # 強制終了
        os._exit(1)
    
    def is_killed(self):
        """
        停止フラグの状態を取得
        
        Returns:
            bool: 停止要求があればTrue
        """
        return self.kill_now.is_set()
    
    def check_and_exit(self, context=""):
        """
        停止フラグをチェックし、必要に応じて例外を発生
        
        Args:
            context: コンテキスト情報
            
        Raises:
            KeyboardInterrupt: 停止要求がある場合
        """
        if self.kill_now.is_set():
            if self.logger and context:
                self.logger.info(f"停止要求により処理を中断: {context}")
            raise KeyboardInterrupt("ユーザーによる停止要求")
    
    def wait_for_signal(self, timeout=None):
        """
        停止シグナルを待機
        
        Args:
            timeout: タイムアウト秒数
            
        Returns:
            bool: タイムアウト前にシグナルを受信したらTrue
        """
        return self.kill_now.wait(timeout)
    
    def reset(self):
        """停止フラグをリセット（テスト用）"""
        self.kill_now.clear()
        self.shutdown_initiated = False