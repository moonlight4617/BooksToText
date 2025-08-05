"""
Kindleスクリーンショット自動化モジュール
Windows版Kindleアプリからページを自動スクリーンショット
"""

import time
import pyautogui
import win32gui
import win32con
import win32api
from pathlib import Path
from PIL import Image
import re
from window_capture import DirectWindowCapture


class KindleScreenshotCapture:
    def __init__(self, logger=None):
        """
        Kindleスクリーンショットキャプチャーの初期化
        
        Args:
            logger: ログインスタンス
        """
        self.logger = logger
        self.kindle_window = None
        self.capture_region = None
        self.page_count = 0
        
        # 設定
        self.page_turn_delay = 2.0  # ページめくり後の待機時間（秒）
        self.screenshot_delay = 0.5  # スクリーンショット前の待機時間
        self.page_turn_key = 'right'  # ページめくりキー（'right', 'space', 'pagedown'）
        
        # Win32直接キャプチャ（マルチモニター対応）
        self.direct_capturer = DirectWindowCapture(logger)
        
        # pyautoguiの安全機能
        pyautogui.FAILSAFE = True  # マウスを左上角に移動で緊急停止
        pyautogui.PAUSE = 0.1  # 各操作間の基本待機時間
        
        self.log_message("Kindleスクリーンショットキャプチャー初期化完了（Win32直接キャプチャ対応）")
    
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
    
    def find_kindle_window(self):
        """
        Kindleアプリのウィンドウを検出（実際のKindleアプリを優先）
        
        Returns:
            bool: 検出成功/失敗
        """
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                if 'kindle' in window_title.lower() or 'kindle' in class_name.lower():
                    windows.append((hwnd, window_title, class_name))
            return True
        
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        
        if not windows:
            self.log_message("Kindleウィンドウが見つかりません", 'error')
            self.log_message("Kindleアプリを起動して書籍を開いてください", 'error')
            return False
        
        # 実際のKindle for PCアプリを優先
        actual_kindle_windows = []
        other_kindle_windows = []
        
        for hwnd, title, class_name in windows:
            self.log_message(f"Kindle関連ウィンドウを検出: '{title}' (クラス: {class_name})", 'debug')
            
            # 実際のKindle for PCアプリを優先
            if 'kindle for pc' in title.lower() or class_name == 'Qt5QWindowIcon':
                actual_kindle_windows.append((hwnd, title, class_name))
            else:
                other_kindle_windows.append((hwnd, title, class_name))
        
        # 実際のKindleアプリが見つかった場合はそれを使用
        if actual_kindle_windows:
            self.kindle_window = actual_kindle_windows[0][0]
            self.log_message(f"実際のKindleアプリを使用: {actual_kindle_windows[0][1]}")
        elif other_kindle_windows:
            self.kindle_window = other_kindle_windows[0][0]
            self.log_message(f"フォールバック: {other_kindle_windows[0][1]}", 'warning')
        else:
            self.log_message("適切なKindleウィンドウが見つかりません", 'error')
            return False
        
        # 他のKindleウィンドウがある場合は警告
        total_windows = len(actual_kindle_windows) + len(other_kindle_windows)
        if total_windows > 1:
            self.log_message(f"複数のKindleウィンドウを検出({total_windows}個)", 'warning')
        
        return True
    
    def activate_kindle_window(self):
        """
        Kindleウィンドウをアクティブ化（Windowsセキュリティ制限対応）
        
        Returns:
            bool: 成功/失敗
        """
        if not self.kindle_window:
            return False
        
        try:
            # ウィンドウを復元
            win32gui.ShowWindow(self.kindle_window, win32con.SW_RESTORE)
            time.sleep(0.2)
            
            # SetForegroundWindowの制限を回避する手法
            try:
                # 現在のスレッドをフォアグラウンドプロセスにアタッチ
                current_thread = win32api.GetCurrentThreadId()
                target_thread, _ = win32gui.GetWindowThreadProcessId(self.kindle_window)
                
                if current_thread != target_thread:
                    win32gui.AttachThreadInput(current_thread, target_thread, True)
                    win32gui.SetForegroundWindow(self.kindle_window)
                    win32gui.AttachThreadInput(current_thread, target_thread, False)
                else:
                    win32gui.SetForegroundWindow(self.kindle_window)
                    
            except Exception as e:
                # フォールバック: 基本的なアクティブ化を試行
                self.log_message(f"高度なアクティブ化に失敗、フォールバック実行: {e}", 'warning')
                try:
                    win32gui.SetForegroundWindow(self.kindle_window)
                except:
                    # 最終フォールバック: ウィンドウの最小化→復元
                    win32gui.ShowWindow(self.kindle_window, win32con.SW_MINIMIZE)
                    time.sleep(0.1)
                    win32gui.ShowWindow(self.kindle_window, win32con.SW_RESTORE)
            
            time.sleep(0.5)  # ウィンドウアクティブ化の待機
            
            # アクティブ化の確認
            active_window = win32gui.GetForegroundWindow()
            if active_window == self.kindle_window:
                self.log_message("Kindleウィンドウをアクティブ化しました")
                return True
            else:
                self.log_message("ウィンドウアクティブ化を試行しましたが、確認できませんでした", 'warning')
                self.log_message("Win32直接キャプチャは影響を受けません", 'info')
                return True  # Win32直接キャプチャでは問題ないのでTrueを返す
            
        except Exception as e:
            self.log_message(f"ウィンドウアクティブ化エラー: {e}", 'error')
            self.log_message("Win32直接キャプチャでは影響ない可能性があります", 'info')
            return True  # Win32直接キャプチャでは影響ないのでTrueを返す
    
    def detect_capture_region(self):
        """
        キャプチャ領域を自動検出（マルチモニター対応）
        
        Returns:
            bool: 検出成功/失敗
        """
        if not self.kindle_window:
            return False
        
        try:
            # ウィンドウの位置・サイズを取得
            rect = win32gui.GetWindowRect(self.kindle_window)
            left, top, right, bottom = rect
            
            self.log_message(f"Kindleウィンドウの座標: ({left}, {top}) - ({right}, {bottom})")
            
            # ウィンドウサイズ計算
            window_width = right - left
            window_height = bottom - top
            
            self.log_message(f"ウィンドウサイズ: {window_width} x {window_height}")
            
            # ウィンドウが有効なサイズかチェック
            if window_width <= 0 or window_height <= 0:
                self.log_message("無効なウィンドウサイズです", 'error')
                return False
            
            # ウィンドウ枠を除いた実際のコンテンツ領域を推定
            # Kindleアプリの場合、通常上部にメニューバー、下部にナビゲーションがある
            margin_top = 80    # 上部メニューバー
            margin_bottom = 60  # 下部ナビゲーション
            margin_left = 20    # 左余白
            margin_right = 20   # 右余白
            
            # 小さなウィンドウの場合はマージンを調整
            if window_height < 300:
                margin_top = 40
                margin_bottom = 30
            if window_width < 400:
                margin_left = 10
                margin_right = 10
            
            content_left = left + margin_left
            content_top = top + margin_top
            content_right = right - margin_right
            content_bottom = bottom - margin_bottom
            
            # コンテンツ領域のサイズ計算
            content_width = content_right - content_left
            content_height = content_bottom - content_top
            
            self.log_message(f"推定コンテンツ領域: ({content_left}, {content_top}) - ({content_right}, {content_bottom})")
            self.log_message(f"コンテンツサイズ: {content_width} x {content_height}")
            
            # コンテンツ領域が有効かチェック
            if content_width <= 0 or content_height <= 0:
                self.log_message("無効なコンテンツ領域サイズです", 'error')
                self.log_message("ウィンドウが小さすぎるか、マージン設定に問題があります", 'error')
                return False
            
            # pyautoguiのregion形式で保存: (left, top, width, height)
            self.capture_region = (content_left, content_top, content_width, content_height)
            
            self.log_message(f"キャプチャ領域設定完了: region=({content_left}, {content_top}, {content_width}, {content_height})")
            
            return True
            
        except Exception as e:
            self.log_message(f"キャプチャ領域検出エラー: {e}", 'error')
            import traceback
            self.log_message(f"詳細: {traceback.format_exc()}", 'debug')
            return False
    
    def set_custom_capture_region(self, x, y, width, height):
        """
        カスタムキャプチャ領域を設定
        
        Args:
            x, y: 左上座標
            width, height: 幅・高さ
        """
        self.capture_region = (x, y, width, height)  # pyautogui region format
        self.log_message(f"カスタムキャプチャ領域設定: region=({x}, {y}, {width}, {height})")
    
    def take_screenshot(self, save_path):
        """
        スクリーンショットを撮影・保存（Win32直接キャプチャ使用）
        
        Args:
            save_path: 保存パス
            
        Returns:
            bool: 成功/失敗
        """
        try:
            time.sleep(self.screenshot_delay)
            
            if not self.kindle_window:
                self.log_message("Kindleウィンドウが設定されていません", 'error')
                return False
            
            # Win32直接キャプチャを使用（マルチモニター対応）
            self.log_message("Win32直接キャプチャでスクリーンショット撮影中", 'debug')
            
            # マージンを考慮した領域キャプチャ
            success = self.direct_capturer.capture_window_region(
                self.kindle_window,
                margin_top=80,
                margin_bottom=60,
                margin_left=20,
                margin_right=20,
                save_path=save_path
            )
            
            if success:
                # ファイルサイズ確認
                file_size = Path(save_path).stat().st_size
                self.log_message(f"スクリーンショット保存完了: {save_path} ({file_size} bytes)")
                
                # 画像が適切なサイズかチェック
                if file_size < 5000:  # 5KB未満の場合は警告
                    self.log_message("スクリーンショットファイルが小さいです。内容を確認してください", 'warning')
                elif file_size > 50000:  # 50KB以上の場合は良好
                    self.log_message("スクリーンショット品質良好", 'debug')
                
                return True
            else:
                self.log_message("Win32直接キャプチャに失敗しました", 'error')
                return False
            
        except Exception as e:
            self.log_message(f"スクリーンショット撮影エラー: {e}", 'error')
            import traceback
            self.log_message(f"詳細: {traceback.format_exc()}", 'debug')
            return False
    
    def turn_page(self):
        """
        ページをめくる
        
        Returns:
            bool: 成功/失敗
        """
        try:
            # Kindleウィンドウがアクティブか確認
            if win32gui.GetForegroundWindow() != self.kindle_window:
                self.activate_kindle_window()
            
            # ページめくり操作
            if self.page_turn_key == 'right':
                pyautogui.press('right')
            elif self.page_turn_key == 'space':
                pyautogui.press('space')
            elif self.page_turn_key == 'pagedown':
                pyautogui.press('pagedown')
            else:
                pyautogui.press('right')  # デフォルト
            
            # ページ読み込み待機
            time.sleep(self.page_turn_delay)
            
            return True
            
        except Exception as e:
            self.log_message(f"ページめくりエラー: {e}", 'error')
            return False
    
    def extract_position_info(self, screenshot_path):
        """
        位置No情報を抽出して進捗を判定
        
        Args:
            screenshot_path: スクリーンショットファイルパス
            
        Returns:
            dict: {'current': int, 'total': int, 'percentage': float} または None
        """
        try:
            from PIL import Image
            import pytesseract
            import re
            
            img = Image.open(screenshot_path)
            width, height = img.size
            
            # 下部ナビゲーション領域を抽出（位置No表示エリア）
            nav_height = int(height * 0.1)  # 下部10%
            nav_region = img.crop((0, height - nav_height, width, height))
            
            # OCR設定（日本語と英語両対応）
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789/%() '
            
            # OCRでテキスト抽出
            text = pytesseract.image_to_string(nav_region, lang='jpn+eng', config=custom_config)
            self.log_message(f"ナビゲーション領域テキスト: '{text.strip()}'", 'debug')
            
            # 位置No形式を検索（複数パターン対応）
            patterns = [
                r'位置No\.?\s*(\d+)\s*/\s*(\d+)\s*\((\d+)%\)',  # 日本語: 位置No. 1234/5678 (23%)
                r'Location\s+(\d+)\s+of\s+(\d+)\s*\((\d+)%\)',  # 英語: Location 1234 of 5678 (23%)
                r'(\d+)\s*/\s*(\d+)\s*\((\d+)%\)',               # 簡易: 1234/5678 (23%)
                r'(\d+)\s+/\s+(\d+)\s+(\d+)%',                  # スペース区切り: 1234 / 5678 23%
                r'(\d{3,})\s*/\s*(\d{3,})',                      # 数字のみ: 1234/5678
            ]
            
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    
                    # パーセンテージ計算
                    if len(match.groups()) >= 3:
                        percentage = int(match.group(3))
                    else:
                        percentage = int((current / total) * 100) if total > 0 else 0
                    
                    result = {
                        'current': current,
                        'total': total,
                        'percentage': percentage,
                        'pattern': i + 1
                    }
                    
                    self.log_message(
                        f"位置No情報を検出: {current}/{total} ({percentage}%) [パターン{i+1}]"
                    )
                    
                    return result
            
            # パターンマッチしない場合のログ
            self.log_message("位置No情報を検出できませんでした", 'debug')
            return None
            
        except Exception as e:
            self.log_message(f"位置No抽出エラー: {e}", 'warning')
            return None
    
    def estimate_total_pages_from_position(self, position_info, current_page):
        """
        位置No情報から総ページ数を推定
        
        Args:
            position_info: 位置No情報辞書
            current_page: 現在のページ番号
        
        Returns:
            int: 推定総ページ数 または None
        """
        if not position_info or position_info['percentage'] <= 0:
            return None
        
        try:
            # 現在の進捗率から総ページ数を推定
            estimated_total = int(current_page / (position_info['percentage'] / 100))
            
            # 合理性チェック
            if estimated_total < current_page or estimated_total > 10000:
                self.log_message(f"推定ページ数が異常です: {estimated_total}", 'warning')
                return None
            
            self.log_message(
                f"総ページ数推定: {estimated_total}ページ "
                f"（現在{current_page}ページ、進捗{position_info['percentage']}%）"
            )
            
            return estimated_total
            
        except Exception as e:
            self.log_message(f"ページ数推定エラー: {e}", 'warning')
            return None
    
    def interactive_continue_check(self, current_page, position_info=None):
        """
        ユーザーに継続確認（位置No情報付き）
        
        Args:
            current_page: 現在のページ番号
            position_info: 位置No情報辞書
            
        Returns:
            bool/str: 継続=True, 終了=False, 自動完了='auto_finish'
        """
        try:
            import msvcrt
            import time
            import threading
            
            # 進捗情報表示
            print("\n" + "="*50)
            print("📊 現在の進捗情報")
            print("="*50)
            
            if position_info:
                percentage = position_info.get('percentage', 0)
                current_pos = position_info.get('current', 0)
                total_pos = position_info.get('total', 0)
                
                print(f"📄 現在のページ: {current_page}")
                print(f"📍 位置No: {current_pos:,}/{total_pos:,} ({percentage}%)")
                
                # プログレスバー表示
                bar_length = 30
                filled_length = int(bar_length * percentage / 100)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                print(f"📈 進捗: |{bar}| {percentage}%")
                
                # 推定残りページ数
                if percentage > 0 and percentage < 100:
                    estimated_remaining = int(current_page * (100 - percentage) / percentage)
                    print(f"📋 推定残りページ: 約{estimated_remaining}ページ")
            else:
                print(f"📄 現在のページ: {current_page}")
                print("📍 位置No情報: 取得できませんでした")
            
            print("\n🤔 次の操作を選択してください:")
            print("  [Enter] 継続 (20ページ進んだら再確認)")
            print("  [a] 自動完了まで継続 (100%まで自動実行)")
            print("  [q] 終了")
            print("\n⏰ 10秒後に自動継続します...")
            
            # 10秒タイマーで自動継続
            user_input = [None]
            
            def get_input():
                if msvcrt.kbhit():
                    user_input[0] = msvcrt.getch().decode('utf-8').lower()
            
            start_time = time.time()
            while time.time() - start_time < 10:
                get_input()
                if user_input[0] is not None:
                    break
                time.sleep(0.1)
            
            choice = user_input[0]
            
            if choice == 'q':
                print("\n🛑 終了を選択しました")
                return False
            elif choice == 'a':
                print("\n🚀 自動完了モードで継続します")
                return 'auto_finish'
            else:
                print("\n▶️  継続します")
                return True
                
        except Exception as e:
            self.log_message(f"継続確認エラー: {e}", 'warning')
            return True  # エラー時は継続
    
    def detect_end_of_book(self, screenshot_path):
        """
        スクリーンショットを解析して書籍終了を検出
        
        Args:
            screenshot_path: スクリーンショットファイルパス
            
        Returns:
            bool: 書籍終了ならTrue
        """
        try:
            from PIL import Image
            import pytesseract
            
            # スクリーンショットを読み込み
            img = Image.open(screenshot_path)
            width, height = img.size
            
            # 下部領域のテキストを抽出（終了判定用）
            bottom_region = img.crop((0, int(height * 0.7), width, height))
            
            # OCRでテキスト抽出
            text = pytesseract.image_to_string(bottom_region, lang='jpn+eng')
            
            # 終了パターンを検出
            end_patterns = [
                "おわり", "終わり", "完", "END", "end",
                "奥付", "参考文献", "索引", "著者略歴",
                "Bibliography", "Index", "About the Author",
                "100%", "位置No.", "Location"
            ]
            
            text_lower = text.lower()
            for pattern in end_patterns:
                if pattern.lower() in text_lower:
                    self.log_message(f"書籍終了パターンを検出: '{pattern}'")
                    return True
            
            return False
            
        except Exception as e:
            self.log_message(f"終了判定エラー: {e}", 'warning')
            return False
    
    def is_last_page(self):
        """
        最後のページかどうかを判定（レガシーメソッド）
        
        Returns:
            bool: 最後のページの場合True
        """
        # detect_end_of_bookまたはextract_position_infoを使用することを推奨
        return False
    
    def smart_capture_with_progress_detection(self, book_name, start_page=1, 
                                            max_pages=None, 
                                            auto_estimate=True,
                                            progress_check_interval=20,
                                            safety_margin=1.2,
                                            output_dir=None):
        """
        進捗検出付きスマートキャプチャ
        
        Args:
            book_name: 書籍名
            start_page: 開始ページ（1から開始）
            max_pages: ユーザー指定の最大ページ数（Noneなら自動推定）
            auto_estimate: 自動推定を有効化
            progress_check_interval: 何ページごとに進捗確認するか
            safety_margin: 推定値に対する安全マージン（1.2 = 20%余裕）
            output_dir: 出力ディレクトリ（Noneの場合はinput/book_name）
            
        Returns:
            int: キャプチャしたページ数
        """
        # 出力ディレクトリ設定
        if output_dir is None:
            output_dir = Path('input') / book_name
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_message(f"📚 スマートページキャプチャ開始: {book_name}")
        self.log_message(f"📁 出力ディレクトリ: {output_dir}")
        self.log_message(f"📊 進捗チェック間隔: {progress_check_interval}ページごと")
        
        if max_pages:
            self.log_message(f"📋 最大ページ数指定: {max_pages}ページ")
        else:
            self.log_message("📋 最大ページ数: 自動推定")
        
        # Kindleウィンドウの準備
        if not self.find_kindle_window():
            return 0
        
        if not self.activate_kindle_window():
            return 0
        
        if not self.detect_capture_region():
            return 0
        
        # キャプチャ開始確認
        self.log_message("\n🚀 5秒後にキャプチャを開始します...")
        self.log_message("⚠️  中止する場合はマウスを画面左上角に移動してください")
        
        for i in range(5, 0, -1):
            self.log_message(f"⏰ 開始まで {i} 秒...")
            time.sleep(1)
        
        # 変数初期化
        captured_count = 0
        current_page = start_page
        estimated_total = None
        user_max_pages = max_pages  # ユーザー指定値を保持
        auto_finish_mode = False
        
        try:
            while True:
                # ファイル名生成
                filename = f"page_{current_page:03d}.png"
                save_path = output_dir / filename
                
                self.log_message(f"📸 ページ {current_page} をキャプチャ中...")
                
                # スクリーンショット撮影
                if self.take_screenshot(save_path):
                    captured_count += 1
                    self.log_message(f"✅ ページ {current_page} 完了: {filename}")
                    
                    # 定期的な進捗確認
                    if captured_count % progress_check_interval == 0:
                        position_info = self.extract_position_info(save_path)
                        
                        if position_info and auto_estimate:
                            # 動的に総ページ数を推定
                            new_estimate = self.estimate_total_pages_from_position(
                                position_info, current_page
                            )
                            
                            if new_estimate:
                                if estimated_total is None:
                                    # 初回推定
                                    estimated_total = int(new_estimate * safety_margin)
                                    self.log_message(f"📊 総ページ数を推定: {estimated_total}ページ（安全マージン込み）")
                                    
                                    # ユーザー指定がない場合は推定値を使用
                                    if max_pages is None:
                                        max_pages = estimated_total
                                else:
                                    # 推定値を更新（大幅な変化がある場合のみ）
                                    if abs(new_estimate - estimated_total/safety_margin) > 20:
                                        estimated_total = int(new_estimate * safety_margin)
                                        if max_pages == user_max_pages:  # ユーザー指定がない場合のみ更新
                                            max_pages = estimated_total
                                            self.log_message(f"📊 総ページ数推定を更新: {estimated_total}ページ")
                        
                        # 終了判定
                        if position_info:
                            percentage = position_info['percentage']
                            
                            # 95%以上で確認（自動完了モードでない場合）
                            if percentage >= 95 and not auto_finish_mode:
                                self.log_message(f"🏁 書籍終了近し（{percentage}%）")
                                continue_decision = self.interactive_continue_check(current_page, position_info)
                                
                                if continue_decision == False:
                                    break
                                elif continue_decision == 'auto_finish':
                                    # 100%まで自動継続
                                    auto_finish_mode = True
                                    max_pages = None  # 制限解除
                                    progress_check_interval = 5  # より頻繁にチェック
                                    self.log_message("🚀 自動完了モードに切り替えました")
                            
                            # 100%で自動終了
                            if percentage >= 100:
                                self.log_message("🎉 書籍100%完了を検出")
                                break
                    
                    # 書籍終了検出
                    if self.detect_end_of_book(save_path):
                        self.log_message("🎯 書籍終了パターンを検出")
                        break
                    
                else:
                    self.log_message(f"❌ ページ {current_page} 失敗", 'error')
                
                # 最大ページ数チェック（安全装置）
                if max_pages and captured_count >= max_pages:
                    self.log_message(f"📋 最大ページ数に到達: {max_pages}ページ")
                    
                    # 最終確認
                    final_position = self.extract_position_info(save_path)
                    if final_position and final_position['percentage'] < 90:
                        self.log_message(f"⚠️  進捗率が低いです（{final_position['percentage']}%）")
                        if self.interactive_continue_check(current_page, final_position):
                            max_pages = int(max_pages * 1.3)  # 30%延長
                            self.log_message(f"📋 最大ページ数を延長: {max_pages}ページ")
                        else:
                            break
                    else:
                        break
                
                # ページめくり
                if not self.turn_page():
                    self.log_message("❌ ページめくり失敗", 'error')
                    break
                
                current_page += 1
                
                # 進捗表示
                if captured_count % 10 == 0:
                    self.log_message(f"📈 進捗: {captured_count} ページ完了")
        
        except pyautogui.FailSafeException:
            self.log_message("🛑 緊急停止が実行されました（マウス左上角移動）", 'warning')
        
        except KeyboardInterrupt:
            self.log_message("⌨️  ユーザーによる中断（Ctrl+C）", 'warning')
        
        except Exception as e:
            self.log_message(f"💥 予期しないエラー: {e}", 'error')
        
        self.log_message(f"🏆 キャプチャ完了: {captured_count} ページ")
        return captured_count
    
    def capture_pages(self, book_name, start_page=1, end_page=None, output_dir=None):
        """
        指定範囲のページをキャプチャ（レガシーメソッド）
        
        Args:
            book_name: 書籍名
            start_page: 開始ページ（1から開始）
            end_page: 終了ページ（Noneの場合は手動停止まで）
            output_dir: 出力ディレクトリ（Noneの場合はinput/book_name）
            
        Returns:
            int: キャプチャしたページ数
        """
        # スマートキャプチャに委譲
        return self.smart_capture_with_progress_detection(
            book_name=book_name,
            start_page=start_page,
            max_pages=end_page,
            auto_estimate=True,
            progress_check_interval=20,
            output_dir=output_dir
        )
        # この部分は smart_capture_with_progress_detection メソッドに移動済み
        pass
    
    def configure_settings(self, page_turn_delay=None, page_turn_key=None, screenshot_delay=None):
        """
        キャプチャ設定の変更
        
        Args:
            page_turn_delay: ページめくり後の待機時間
            page_turn_key: ページめくりキー
            screenshot_delay: スクリーンショット前の待機時間
        """
        if page_turn_delay is not None:
            self.page_turn_delay = page_turn_delay
            self.log_message(f"ページめくり待機時間: {page_turn_delay}秒")
        
        if page_turn_key is not None:
            self.page_turn_key = page_turn_key
            self.log_message(f"ページめくりキー: {page_turn_key}")
        
        if screenshot_delay is not None:
            self.screenshot_delay = screenshot_delay
            self.log_message(f"スクリーンショット待機時間: {screenshot_delay}秒")


def main():
    """スクリーンショット機能のテスト用メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kindleスクリーンショット自動キャプチャ')
    parser.add_argument('--book', required=True, help='書籍名（保存フォルダ名）')
    parser.add_argument('--start', type=int, default=1, help='開始ページ番号')
    parser.add_argument('--end', type=int, help='終了ページ番号（未指定時は手動停止）')
    parser.add_argument('--delay', type=float, default=2.0, help='ページめくり待機時間（秒）')
    parser.add_argument('--key', default='right', choices=['right', 'space', 'pagedown'], 
                       help='ページめくりキー')
    
    args = parser.parse_args()
    
    # キャプチャ実行
    capturer = KindleScreenshotCapture()
    capturer.configure_settings(
        page_turn_delay=args.delay,
        page_turn_key=args.key
    )
    
    captured_count = capturer.capture_pages(
        book_name=args.book,
        start_page=args.start,
        end_page=args.end
    )
    
    print(f"\n完了: {captured_count} ページをキャプチャしました")


if __name__ == '__main__':
    main()