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
        # 成功率の高い設定を優先順序で配置
        self.ocr_configs = [
            r'--oem 3 --psm 3 -l jpn',   # 完全な自動ページセグメンテーション（最も成功率が高い）
            r'--oem 3 --psm 6 -l jpn',   # 単一の均一テキストブロック
            r'--oem 3 --psm 4 -l jpn',   # 可変サイズの単一テキスト列
            r'--oem 3 --psm 1 -l jpn',   # OSD付き自動ページセグメンテーション
            r'--oem 3 --psm 11 -l jpn',  # スパーステキスト
            r'--oem 3 --psm 8 -l jpn',   # 単語レベル（図表内の小さなテキスト）
            r'--oem 3 --psm 7 -l jpn',   # 単一テキスト行（図表キャプション）
            r'--oem 3 --psm 12 -l jpn',  # 単語レベル・スパーステキスト（図中ラベル）
            r'--oem 3 --psm 13 -l jpn',  # 生の行・文字の境界を検出しない
        ]
        
        # デフォルト設定
        self.default_config = self.ocr_configs[0]
    
    def extract_text(self, image):
        """
        画像からテキストを抽出（高速化された複数設定での比較処理）
        
        Args:
            image: PIL.Image オブジェクト
            
        Returns:
            str: 抽出されたテキスト
        """
        try:
            # 複数のOCR設定で処理し、早期終了による高速化
            best_text = ""
            best_confidence = 0.0
            
            for i, config in enumerate(self.ocr_configs):
                try:
                    # OCRとデータを同時取得（効率化）
                    data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
                    
                    # 信頼度計算
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    confidence = sum(confidences) / len(confidences) if confidences else 0.0
                    
                    # テキスト抽出（dataから復元）
                    words = []
                    for j, word in enumerate(data['text']):
                        if int(data['conf'][j]) > 0 and word.strip():
                            words.append(word)
                    text = ' '.join(words)
                    
                    # 品質チェック
                    if self._is_sufficient_quality(text, confidence):
                        best_text = text
                        best_confidence = confidence
                        
                        # 早期終了条件：高品質な結果が得られた場合
                        if confidence > 85.0 and len(text.strip()) > 10:
                            print(f"高信頼度で早期終了 (設定{i+1}/{len(self.ocr_configs)}): {confidence:.1f}%")
                            break
                    
                    # より良い結果の場合は更新
                    if confidence > best_confidence and len(text.strip()) > 0:
                        best_text = text
                        best_confidence = confidence
                        
                except Exception as e:
                    print(f"OCR設定 {config} でエラー: {e}")
                    continue
            
            # フォールバック: すべて失敗した場合は図表向け処理を追加
            if not best_text.strip():
                best_text = self._extract_sparse_text_with_enhanced_processing(image)
            
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
    
    def _is_sufficient_quality(self, text, confidence):
        """
        テキスト品質が十分かを判定
        
        Args:
            text: 抽出されたテキスト
            confidence: OCR信頼度
            
        Returns:
            bool: 品質が十分な場合True
        """
        if not text or not text.strip():
            return False
            
        text_length = len(text.strip())
        
        # 段階的品質判定
        if confidence > 80.0 and text_length > 5:
            return True
        elif confidence > 70.0 and text_length > 15:
            return True
        elif confidence > 60.0 and text_length > 30:
            return True
        
        return False
    
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
    
    def _extract_sparse_text(self, image):
        """
        図表ページ向けのスパーステキスト抽出（高速化版）
        
        Args:
            image: PIL.Image オブジェクト
            
        Returns:
            str: 抽出されたテキスト
        """
        try:
            # 図表向け特殊設定（効果的な順序で配置）
            sparse_configs = [
                r'--oem 3 --psm 8 -l jpn',   # 単語レベル（最も効果的）
                r'--oem 3 --psm 7 -l jpn',   # 単一行
                r'--oem 3 --psm 12 -l jpn',  # スパース単語
                r'--oem 3 --psm 13 -l jpn',  # 生の行
            ]
            
            extracted_parts = []
            
            for config in sparse_configs:
                try:
                    # 効率化：image_to_dataを使用して同時処理
                    data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
                    
                    # 信頼度チェック付きでテキスト復元
                    words = []
                    confidences = []
                    for j, word in enumerate(data['text']):
                        conf = int(data['conf'][j])
                        if conf > 30 and word.strip():  # より緩い閾値
                            words.append(word)
                            confidences.append(conf)
                    
                    if words:
                        text = ' '.join(words)
                        avg_confidence = sum(confidences) / len(confidences)
                        
                        if text.strip() and avg_confidence > 40:
                            extracted_parts.append(text.strip())
                            print(f"スパース抽出成功 (信頼度{avg_confidence:.1f}%): '{text.strip()[:50]}...'")
                            
                            # 早期終了：十分なテキストが取得できた場合
                            if len(text.strip()) > 20 and avg_confidence > 60:
                                break
                        
                except Exception as e:
                    print(f"スパース設定 {config} でエラー: {e}")
                    continue
            
            # 抽出されたテキストがある場合は結合
            if extracted_parts:
                combined_text = ' '.join(extracted_parts)
                return combined_text
            
            # それでも失敗した場合は代替テキストを返す
            return "[図表ページ - テキスト抽出困難]"
            
        except Exception as e:
            print(f"スパーステキスト抽出エラー: {e}")
            return "[図表ページ - 処理エラー]"
    
    def _extract_sparse_text_with_enhanced_processing(self, image):
        """
        図表向け画像前処理を含むスパーステキスト抽出
        通常のOCRが失敗した場合のみ実行される高負荷処理
        
        Args:
            image: PIL.Image オブジェクト
            
        Returns:
            str: 抽出されたテキスト
        """
        try:
            print("図表向け特殊処理を開始...")
            
            # まず通常のスパース抽出を試行
            sparse_result = self._extract_sparse_text(image)
            if sparse_result.strip() and not sparse_result.startswith("[図表ページ"):
                return sparse_result
            
            # 図表向け前処理を適用
            from utils import ImageUtils
            image_utils = ImageUtils()
            
            # PIL ImageをOpenCVに変換して図表向け処理
            enhanced_image = image_utils._enhance_image_for_charts(image)
            
            if enhanced_image:
                # 拡張処理後のOCR実行
                enhanced_result = self._extract_sparse_text(enhanced_image)
                if enhanced_result.strip() and not enhanced_result.startswith("[図表ページ"):
                    print("図表向け前処理により抽出成功")
                    return enhanced_result
            
            # 最終的にも失敗した場合
            return "[図表ページ - テキスト抽出困難]"
            
        except Exception as e:
            print(f"図表向け特殊処理エラー: {e}")
            return "[図表ページ - 処理エラー]"