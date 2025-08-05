"""
Direct Window Capture Module for Multi-Monitor Environment
Win32 APIを使用してウィンドウを直接キャプチャ
"""

import win32gui
import win32ui
import win32con
import win32api
from PIL import Image
import numpy as np
from ctypes import windll
from ctypes.wintypes import RECT


class DirectWindowCapture:
    """Win32 APIを使用した直接ウィンドウキャプチャクラス"""
    
    def __init__(self, logger=None):
        self.logger = logger
    
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
    
    def capture_window(self, hwnd, save_path=None, content_only=True):
        """
        指定されたウィンドウを直接キャプチャ
        
        Args:
            hwnd: ウィンドウハンドル
            save_path: 保存パス（Noneの場合はPIL Imageを返す）
            content_only: Trueの場合はコンテンツ領域のみ、Falseの場合はウィンドウ全体
            
        Returns:
            PIL.Image: キャプチャした画像（save_pathがNoneの場合）
            bool: 保存成功/失敗（save_pathが指定された場合）
        """
        try:
            # ウィンドウを復元
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            # SetForegroundWindowの制限を回避（ベストエフォート）
            try:
                current_thread = win32api.GetCurrentThreadId()
                target_thread, _ = win32gui.GetWindowThreadProcessId(hwnd)
                
                if current_thread != target_thread:
                    win32gui.AttachThreadInput(current_thread, target_thread, True)
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.AttachThreadInput(current_thread, target_thread, False)
                else:
                    win32gui.SetForegroundWindow(hwnd)
            except:
                # フォアグラウンド設定に失敗してもキャプチャには影響しない
                self.log_message("フォアグラウンド設定をスキップ（Win32直接キャプチャには影響なし）", 'debug')
            
            # 少し待機
            import time
            time.sleep(0.3)
            
            # ウィンドウの位置とサイズを取得
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            
            self.log_message(f"ウィンドウサイズ: {width} x {height}")
            
            # クライアント領域のサイズを取得（タイトルバーなどを除く）
            if content_only:
                client_rect = win32gui.GetClientRect(hwnd)
                client_width = client_rect[2]
                client_height = client_rect[3]
                self.log_message(f"クライアント領域サイズ: {client_width} x {client_height}")
                capture_width = client_width
                capture_height = client_height
            else:
                capture_width = width
                capture_height = height
            
            # デバイスコンテキストの取得
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            
            # ビットマップの作成
            save_bitmap = win32ui.CreateBitmap()
            save_bitmap.CreateCompatibleBitmap(mfc_dc, capture_width, capture_height)
            save_dc.SelectObject(save_bitmap)
            
            # ウィンドウの内容をコピー
            if content_only:
                # クライアント領域のみをコピー
                result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 1)
            else:
                # ウィンドウ全体をコピー
                result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)
            
            # ビットマップデータを取得
            bmpinfo = save_bitmap.GetInfo()
            bmpstr = save_bitmap.GetBitmapBits(True)
            
            # PILイメージに変換
            image = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )
            
            # リソースの解放
            win32gui.DeleteObject(save_bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            
            self.log_message(f"キャプチャ完了: {image.size}")
            
            if save_path:
                image.save(save_path, 'PNG')
                self.log_message(f"画像保存: {save_path}")
                return True
            else:
                return image
                
        except Exception as e:
            self.log_message(f"ウィンドウキャプチャエラー: {e}", 'error')
            import traceback
            self.log_message(f"詳細: {traceback.format_exc()}", 'debug')
            return False if save_path else None
    
    def capture_window_region(self, hwnd, margin_top=80, margin_bottom=60, 
                            margin_left=20, margin_right=20, save_path=None):
        """
        ウィンドウの特定領域をキャプチャ（マージンを考慮）
        
        Args:
            hwnd: ウィンドウハンドル
            margin_*: 各方向のマージン
            save_path: 保存パス
            
        Returns:
            PIL.Image or bool: キャプチャした画像または成功/失敗
        """
        try:
            # まずウィンドウ全体をキャプチャ
            full_image = self.capture_window(hwnd, content_only=True)
            if not full_image:
                return False if save_path else None
            
            # 画像サイズを取得
            img_width, img_height = full_image.size
            
            # マージンを調整（画像サイズに応じて）
            if img_height < 300:
                margin_top = max(10, margin_top // 2)
                margin_bottom = max(10, margin_bottom // 2)
            if img_width < 400:
                margin_left = max(10, margin_left // 2)
                margin_right = max(10, margin_right // 2)
            
            # クロップ領域を計算
            crop_left = margin_left
            crop_top = margin_top
            crop_right = img_width - margin_right
            crop_bottom = img_height - margin_bottom
            
            # 有効な領域かチェック
            if crop_right <= crop_left or crop_bottom <= crop_top:
                self.log_message("無効なクロップ領域", 'error')
                return False if save_path else None
            
            # 画像をクロップ
            cropped_image = full_image.crop((crop_left, crop_top, crop_right, crop_bottom))
            
            self.log_message(f"クロップ完了: {cropped_image.size}")
            
            if save_path:
                cropped_image.save(save_path, 'PNG')
                self.log_message(f"クロップ画像保存: {save_path}")
                return True
            else:
                return cropped_image
                
        except Exception as e:
            self.log_message(f"領域キャプチャエラー: {e}", 'error')
            return False if save_path else None