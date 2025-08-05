"""
ユーティリティ関数モジュール
画像処理、ファイル操作等の補助機能
"""

import os
from pathlib import Path
from PIL import Image, ImageEnhance
import cv2
import numpy as np


class ImageUtils:
    def __init__(self, logger=None):
        # サポートする画像拡張子
        self.supported_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        self.logger = logger
    
    def _log_message(self, message, level='debug'):
        """ログ出力のヘルパーメソッド"""
        if self.logger:
            if level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
            elif level == 'info':
                self.logger.info(message)
            else:
                self.logger.debug(message)
        else:
            print(message)
    
    def get_image_files(self, directory):
        """
        ディレクトリから画像ファイルを取得（ファイル名順でソート）
        
        Args:
            directory: 画像ファイルのディレクトリパス
            
        Returns:
            list: ソートされた画像ファイルパスのリスト
        """
        directory = Path(directory)
        image_files = []
        
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                image_files.append(file_path)
        
        # ファイル名でソート
        image_files.sort(key=lambda x: x.name)
        
        return image_files
    
    def preprocess_image(self, image_path):
        """
        OCR用画像前処理
        
        Args:
            image_path: 画像ファイルパス
            
        Returns:
            PIL.Image: 前処理済み画像
        """
        try:
            # 画像読み込み
            image = Image.open(image_path)
            
            # RGBに変換（必要に応じて）
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 画像前処理
            processed_image = self._enhance_image(image)
            
            return processed_image
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"画像前処理エラー: {e}")
            else:
                print(f"画像前処理エラー: {e}")
            return None
    
    def _enhance_image(self, image):
        """
        画像品質向上処理（OCR精度向上のための高度な前処理）
        
        Args:
            image: PIL.Image オブジェクト
            
        Returns:
            PIL.Image: 品質向上済み画像
        """
        # OpenCV形式に変換
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # 1. 解像度アップスケーリング（2倍）
        height, width = opencv_image.shape[:2]
        opencv_image = cv2.resize(opencv_image, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
        
        # 2. グレースケール変換（OCR最適化）
        gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
        
        # 3. ノイズ除去（Non-local Means Denoising）
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # 4. コントラスト強化（CLAHE: Contrast Limited Adaptive Histogram Equalization）
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        contrast_enhanced = clahe.apply(denoised)
        
        # 5. 傾き補正
        deskewed = self._deskew_image(contrast_enhanced)
        
        # 6. モルフォロジー処理（文字の鮮明化）
        kernel = np.ones((1,1), np.uint8)
        morphed = cv2.morphologyEx(deskewed, cv2.MORPH_CLOSE, kernel)
        
        # 7. 二値化（Otsuの手法）
        _, binary = cv2.threshold(morphed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 8. 小さなノイズ除去
        cleaned = self._remove_small_noise(binary)
        
        # PIL形式に戻す
        result = Image.fromarray(cleaned)
        
        return result
    
    def _denoise_image(self, image):
        """
        ノイズ除去（OpenCV使用）
        
        Args:
            image: PIL.Image オブジェクト
            
        Returns:
            PIL.Image: ノイズ除去済み画像
        """
        try:
            # PIL → OpenCV変換
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # ノイズ除去
            denoised = cv2.bilateralFilter(opencv_image, 9, 75, 75)
            
            # OpenCV → PIL変換
            result = Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))
            
            return result
            
        except Exception as e:
            print(f"ノイズ除去エラー: {e}")
            return image  # エラー時は元画像を返す


    def _deskew_image(self, image):
        """
        画像の傾き補正
        
        Args:
            image: グレースケール画像（numpy array）
            
        Returns:
            numpy array: 傾き補正済み画像
        """
        try:
            # 画像のサイズチェック
            if image is None or image.size == 0:
                self._log_message("傾き補正スキップ: 無効な画像", 'warning')
                return image
            
            # Hough変換による直線検出
            edges = cv2.Canny(image, 50, 150, apertureSize=3)
            
            # エッジが検出されない場合はスキップ
            if edges is None or np.sum(edges) == 0:
                self._log_message("傾き補正スキップ: エッジが検出されませんでした", 'debug')
                return image
            
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None and len(lines) > 0:
                # 角度の計算
                angles = []
                max_lines = min(10, len(lines))  # 安全なスライス
                
                for i in range(max_lines):
                    line = lines[i]
                    if line is not None and len(line) > 0:
                        rho, theta = line[0]
                        angle = theta * 180 / np.pi
                        
                        # 角度を-90〜90度の範囲に正規化
                        if angle > 90:
                            angle = angle - 180
                        elif angle < -90:
                            angle = angle + 180
                        
                        # 有効な角度範囲のみ考慮
                        if -45 <= angle <= 45:
                            angles.append(angle)
                
                if angles and len(angles) >= 3:  # 最低3本の線が必要
                    # 中央値を使用して傾き角度を決定
                    skew_angle = np.median(angles)
                    
                    # 傾きが0.5度以上の場合のみ補正
                    if abs(skew_angle) > 0.5 and abs(skew_angle) < 30:  # 最大30度まで
                        # 回転変換
                        (h, w) = image.shape[:2]
                        center = (w // 2, h // 2)
                        
                        rotation_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
                        deskewed = cv2.warpAffine(image, rotation_matrix, (w, h), 
                                                flags=cv2.INTER_CUBIC, 
                                                borderMode=cv2.BORDER_REPLICATE)
                        
                        self._log_message(f"傾き補正実行: {skew_angle:.2f}度", 'debug')
                        return deskewed
                    else:
                        self._log_message(f"傾き補正スキップ: 角度が範囲外 ({skew_angle:.2f}度)", 'debug')
                else:
                    self._log_message(f"傾き補正スキップ: 有効な線が不足 ({len(angles)}本)", 'debug')
            else:
                self._log_message("傾き補正スキップ: 直線が検出されませんでした", 'debug')
            
            return image
            
        except Exception as e:
            self._log_message(f"傾き補正エラー: {e}", 'error')
            import traceback
            self._log_message(f"詳細: {traceback.format_exc()}", 'error')
            return image
    
    def _remove_small_noise(self, binary_image):
        """
        小さなノイズ除去
        
        Args:
            binary_image: 二値化画像（numpy array）
            
        Returns:
            numpy array: ノイズ除去済み画像
        """
        try:
            # 連結成分分析でノイズ除去
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_image, connectivity=8)
            
            # 小さな成分を除去
            min_size = 50  # 最小成分サイズ
            cleaned = np.zeros_like(binary_image)
            
            for i in range(1, num_labels):  # 0は背景なので除外
                if stats[i, cv2.CC_STAT_AREA] >= min_size:
                    cleaned[labels == i] = 255
            
            return cleaned
            
        except Exception as e:
            print(f"ノイズ除去エラー: {e}")
            return binary_image
    
    def _detect_text_regions(self, image):
        """
        文字領域検出
        
        Args:
            image: グレースケール画像（numpy array）
            
        Returns:
            list: 検出された文字領域のリスト
        """
        try:
            # MSER（Maximally Stable Extremal Regions）による文字領域検出
            mser = cv2.MSER_create(
                _delta=5,
                _min_area=60,
                _max_area=14400,
                _max_variation=0.25,
                _min_diversity=0.2,
                _max_evolution=200,
                _area_threshold=1.01,
                _min_margin=0.003,
                _edge_blur_size=5
            )
            
            regions, _ = mser.detectRegions(image)
            
            # バウンディングボックスに変換
            text_regions = []
            for region in regions:
                x, y, w, h = cv2.boundingRect(region.reshape(-1, 1, 2))
                text_regions.append((x, y, w, h))
            
            return text_regions
            
        except Exception as e:
            print(f"文字領域検出エラー: {e}")
            return []


class TextUtils:
    @staticmethod
    def clean_text(text):
        """
        テキストのクリーニング
        
        Args:
            text: 元のテキスト
            
        Returns:
            str: クリーニング済みテキスト
        """
        if not text:
            return ""
        
        # 複数の空行を1つにまとめる
        import re
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        
        # 行末の不要な空白を除去
        lines = text.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        
        return '\n'.join(cleaned_lines)
    
    @staticmethod
    def split_by_pages(text, page_marker='---PAGE---'):
        """
        テキストをページごとに分割
        
        Args:
            text: 結合されたテキスト
            page_marker: ページ区切り文字
            
        Returns:
            list: ページごとのテキストリスト
        """
        if page_marker in text:
            return text.split(page_marker)
        else:
            return [text]