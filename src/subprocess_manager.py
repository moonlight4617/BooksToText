"""
サブプロセス管理モジュール
キャンセル可能なsubprocess実行と適切なプロセス終了処理
"""

import subprocess
import os
import signal
import time
import threading
import sys
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class ManagedSubprocess:
    """
    キャンセル可能なサブプロセス管理クラス
    プロセスグループを使用して子プロセス全体を適切に管理
    """
    
    def __init__(self, logger=None):
        """
        初期化
        
        Args:
            logger: ログインスタンス
        """
        self.logger = logger
        self.process = None
        self.process_group = None
        self.monitor_thread = None
        self.shutdown_event = threading.Event()
        
        if self.logger:
            self.logger.debug("ManagedSubprocessを初期化しました")
    
    def run_with_cancellation(self, cmd, killer=None, timeout=None, check_interval=0.5):
        """
        キャンセル可能なsubprocess実行
        
        Args:
            cmd: 実行するコマンド（リストまたは文字列）
            killer: GracefulKillerインスタンス
            timeout: タイムアウト秒数
            check_interval: チェック間隔（秒）
            
        Returns:
            int: リターンコード（中断時はNone）
        """
        if self.logger:
            cmd_str = ' '.join(cmd) if isinstance(cmd, list) else str(cmd)
            self.logger.info(f"サブプロセス実行開始: {cmd_str}")
        
        start_time = time.time()
        
        try:
            # プロセス作成設定
            creation_flags = 0
            preexec_fn = None
            
            if os.name == 'nt':  # Windows
                # CREATE_NEW_PROCESS_GROUPでプロセスグループ作成
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
            else:  # Unix系
                # 新しいプロセスグループのリーダーとして起動
                preexec_fn = os.setsid
            
            # プロセス開始
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags,
                preexec_fn=preexec_fn,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            if self.logger:
                self.logger.debug(f"プロセス開始: PID={self.process.pid}")
            
            # 出力読み取りスレッドを開始
            self._start_output_threads()
            
            # プロセス監視ループ
            while self.process.poll() is None:
                # キャンセルチェック
                if killer and killer.is_killed():
                    if self.logger:
                        self.logger.warning("キャンセル要求を受信しました")
                    self._terminate_process_tree()
                    return None
                
                # タイムアウトチェック
                if timeout and (time.time() - start_time) > timeout:
                    if self.logger:
                        self.logger.error(f"プロセスがタイムアウトしました ({timeout}秒)")
                    self._terminate_process_tree()
                    return None
                
                time.sleep(check_interval)
            
            # 正常終了
            returncode = self.process.returncode
            elapsed_time = time.time() - start_time
            
            # 出力スレッドの終了を待機
            self.shutdown_event.set()
            
            if self.logger:
                if returncode == 0:
                    self.logger.info(f"サブプロセス正常終了 (実行時間: {elapsed_time:.1f}秒)")
                else:
                    self.logger.warning(f"サブプロセス異常終了: code={returncode} (実行時間: {elapsed_time:.1f}秒)")
            
            return returncode
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"サブプロセス実行エラー: {e}")
            self._terminate_process_tree()
            return None
        
        finally:
            self.shutdown_event.set()
            self.process = None
    
    def _start_output_threads(self):
        """標準出力・標準エラー出力を読み取るスレッドを開始"""
        if not self.process:
            return
        
        def read_stdout():
            if self.process and self.process.stdout:
                try:
                    for line in iter(self.process.stdout.readline, ''):
                        if self.shutdown_event.is_set():
                            break
                        if line.strip() and self.logger:
                            self.logger.debug(f"STDOUT: {line.strip()}")
                except Exception:
                    pass
        
        def read_stderr():
            if self.process and self.process.stderr:
                try:
                    for line in iter(self.process.stderr.readline, ''):
                        if self.shutdown_event.is_set():
                            break
                        if line.strip() and self.logger:
                            self.logger.warning(f"STDERR: {line.strip()}")
                except Exception:
                    pass
        
        # 出力読み取りスレッドを開始
        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()
    
    def _terminate_process_tree(self):
        """プロセスツリー全体を終了"""
        if not self.process:
            return
        
        try:
            if self.logger:
                self.logger.info(f"プロセスツリーを終了します: PID={self.process.pid}")
            
            if os.name == 'nt':  # Windows
                self._terminate_windows_process_tree()
            else:  # Unix系
                self._terminate_unix_process_tree()
            
            if self.logger:
                self.logger.info("プロセスツリーを正常に終了しました")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"プロセス終了エラー: {e}")
    
    def _terminate_windows_process_tree(self):
        """Windows用プロセスツリー終了"""
        try:
            # まずCTRL_BREAK_EVENTを送信
            os.kill(self.process.pid, signal.CTRL_BREAK_EVENT)
            
            # 3秒待機
            try:
                self.process.wait(timeout=3)
                return  # 正常終了
            except subprocess.TimeoutExpired:
                pass
            
            # psutilが利用可能な場合は子プロセスも含めて終了
            if HAS_PSUTIL:
                try:
                    parent = psutil.Process(self.process.pid)
                    children = parent.children(recursive=True)
                    
                    # 子プロセスを先に終了
                    for child in children:
                        try:
                            child.terminate()
                        except psutil.NoSuchProcess:
                            pass
                    
                    # 親プロセスを終了
                    parent.terminate()
                    
                    # 1秒待機後、まだ生きていれば強制終了
                    time.sleep(1)
                    for child in children:
                        try:
                            if child.is_running():
                                child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    
                    if parent.is_running():
                        parent.kill()
                        
                except psutil.NoSuchProcess:
                    pass  # プロセスが既に終了している
            else:
                # psutilがない場合はtaskkillを使用
                subprocess.run([
                    'taskkill', '/F', '/T', '/PID', str(self.process.pid)
                ], capture_output=True)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Windows プロセス終了エラー: {e}")
    
    def _terminate_unix_process_tree(self):
        """Unix系用プロセスツリー終了"""
        try:
            # プロセスグループにSIGTERMを送信
            pgid = os.getpgid(self.process.pid)
            os.killpg(pgid, signal.SIGTERM)
            
            # 3秒待機
            try:
                self.process.wait(timeout=3)
                return  # 正常終了
            except subprocess.TimeoutExpired:
                pass
            
            # SIGKILLで強制終了
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # プロセスグループが既に存在しない
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Unix プロセス終了エラー: {e}")
    
    def is_running(self):
        """
        プロセスが実行中かチェック
        
        Returns:
            bool: 実行中ならTrue
        """
        return self.process is not None and self.process.poll() is None
    
    def get_pid(self):
        """
        プロセスIDを取得
        
        Returns:
            int: プロセスID（プロセスがない場合はNone）
        """
        return self.process.pid if self.process else None