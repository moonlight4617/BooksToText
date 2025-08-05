"""
OCR処理モジュール
Tesseract OCRを使用した画像からテキスト抽出
"""

import pytesseract
from PIL import Image
import re


class OCRProcessor:
    def __init__(self):
        # Windows環境でのTesseract実行ファイルパス設定
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        
        # 複数のOCR設定（PSM: Page Segmentation Mode）
        self.ocr_configs = [
            r'--oem 3 --psm 6 -l jpn',   # 単一の均一テキストブロック
            r'--oem 3 --psm 3 -l jpn',   # 完全な自動ページセグメンテーション
            r'--oem 3 --psm 4 -l jpn',   # 可変サイズの単一テキスト列
            r'--oem 3 --psm 1 -l jpn',   # OSD付き自動ページセグメンテーション
            r'--oem 3 --psm 11 -l jpn',  # スパーステキスト
        ]
        
        # デフォルト設定
        self.default_config = self.ocr_configs[0]
    
    def extract_text(self, image):
        """
        画像からテキストを抽出（複数設定での比較処理）
        
        Args:
            image: PIL.Image オブジェクト
            
        Returns:
            str: 抽出されたテキスト
        """
        try:
            # 複数のOCR設定で処理し、最も信頼度の高い結果を選択
            best_text = ""
            best_confidence = 0.0
            
            for config in self.ocr_configs:
                try:
                    # OCR実行
                    text = pytesseract.image_to_string(image, config=config)
                    
                    # 信頼度取得
                    confidence = self._get_confidence_for_config(image, config)
                    
                    # より良い結果の場合は更新
                    if confidence > best_confidence and len(text.strip()) > 0:
                        best_text = text
                        best_confidence = confidence
                        
                except Exception as e:
                    print(f"OCR設定 {config} でエラー: {e}")
                    continue
            
            # フォールバック: すべて失敗した場合はデフォルト設定で再試行
            if not best_text.strip():
                best_text = pytesseract.image_to_string(image, config=self.default_config)
            
            # テキスト後処理
            cleaned_text = self._postprocess_text(best_text)
            
            print(f"OCR信頼度: {best_confidence:.1f}%")
            
            return cleaned_text
            
        except Exception as e:
            print(f"OCRエラー: {e}")
            return ""
    
    def _postprocess_text(self, text):
        """
        抽出テキストの後処理
        
        Args:
            text: 生のOCRテキスト
            
        Returns:
            str: 後処理済みテキスト
        """
        if not text:
            return ""
        
        # 不要な改行を除去
        text = re.sub(r'\n+', '\n', text)
        
        # 先頭・末尾の空白除去
        text = text.strip()
        
        # 明らかな誤認識文字の修正（必要に応じて追加）
        # text = text.replace('〇', 'O')  # 例
        
        return text
    
    def _get_confidence_for_config(self, image, config):
        """
        指定されたOCR設定での信頼度を取得
        
        Args:
            image: PIL.Image オブジェクト
            config: OCR設定文字列
            
        Returns:
            float: 信頼度（0-100）
        """
        try:
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            
            if confidences:
                return sum(confidences) / len(confidences)
            else:
                return 0.0
                
        except Exception as e:
            print(f"信頼度取得エラー: {e}")
            return 0.0
    
    def get_confidence(self, image):
        """
        OCR信頼度を取得（デフォルト設定使用）
        
        Args:
            image: PIL.Image オブジェクト
            
        Returns:
            float: 信頼度（0-100）
        """
        return self._get_confidence_for_config(image, self.default_config)
    
    def extract_text_with_regions(self, image, text_regions=None):
        """
        文字領域を指定してテキスト抽出
        
        Args:
            image: PIL.Image オブジェクト
            text_regions: 文字領域のリスト [(x, y, w, h), ...]
            
        Returns:
            str: 抽出されたテキスト
        """
        if not text_regions:
            return self.extract_text(image)
        
        extracted_texts = []
        
        for x, y, w, h in text_regions:
            try:
                # 領域を切り出し
                region = image.crop((x, y, x + w, y + h))
                
                # OCR実行
                text = self.extract_text(region)
                if text.strip():
                    extracted_texts.append(text.strip())
                    
            except Exception as e:
                print(f"領域OCRエラー: {e}")
                continue
        
        return '\n'.join(extracted_texts)