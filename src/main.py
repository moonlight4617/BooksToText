#!/usr/bin/env python3
"""
Kindle to Text Converter - Main Script
Kindle書籍のスクリーンショット画像をOCRでテキストに変換
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from ocr_processor import OCRProcessor
from utils import ImageUtils
from logger import Logger
from error_handler import ErrorHandler, OCRError, FileProcessError
from progress_tracker import ProgressTracker
from parallel_processor import ParallelOCRProcessor, AdaptiveProcessor
from signal_handler import GracefulKiller


def main():
    parser = argparse.ArgumentParser(description='Kindle書籍のOCRテキスト変換')
    parser.add_argument('--book', required=True, help='書籍名（inputフォルダ内のサブフォルダ名）')
    parser.add_argument('--resume', action='store_true', help='中断したところから再開')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='ログレベル')
    parser.add_argument('--parallel', action='store_true', 
                       help='並列処理を有効化（高速化）')
    parser.add_argument('--workers', type=int, default=None,
                       help='並列処理ワーカー数（自動設定時はNone）')
    parser.add_argument('--no-progress', action='store_true',
                       help='進捗表示を無効化')
    args = parser.parse_args()
    
    # ログ初期化
    logger = Logger(log_level=getattr(logging, args.log_level))
    error_handler = ErrorHandler(logger)
    
    # シグナルハンドラー初期化
    killer = GracefulKiller(logger)
    
    book_name = args.book
    input_dir = Path('input') / book_name
    output_dir = Path('output')
    output_file = output_dir / f'{book_name}.txt'
    checkpoint_file = Path('temp') / f'{book_name}_checkpoint.json'
    
    start_time = time.time()
    success_count = 0
    error_count = 0
    
    try:
        logger.info("=" * 50)
        logger.info(f"Kindle OCR処理開始: {book_name}")
        logger.info(f"ログレベル: {args.log_level}")
        logger.info("=" * 50)
        
        # 入力ディレクトリ検証
        image_files = error_handler.validate_input_directory(input_dir)
        
        # 出力ディレクトリ検証
        error_handler.validate_output_directory(output_dir)
        error_handler.validate_output_directory(Path('temp'))
        
        # チェックポイント読み込み（再開モード）
        processed_files = []
        start_index = 0
        
        if args.resume:
            checkpoint_data = error_handler.load_progress_checkpoint(checkpoint_file)
            if checkpoint_data:
                processed_files = [Path(f) for f in checkpoint_data.get('processed_files', [])]
                start_index = checkpoint_data.get('current_index', 0)
                logger.info(f"処理を再開: {start_index}番目から")
        
        # ログ処理開始
        logger.log_processing_start(book_name, len(image_files))
        
        # 処理済みファイルがある場合は除外
        if processed_files:
            remaining_files = [f for f in image_files if f not in processed_files]
            image_files = remaining_files
        
        if not image_files:
            logger.info("すべてのファイルが処理済みです")
            return
        
        # 適応的プロセッサーで最適な設定を取得
        adaptive_processor = AdaptiveProcessor(logger)
        optimal_settings = adaptive_processor.get_recommended_settings()
        
        # 並列処理設定
        use_parallel = args.parallel or optimal_settings['use_parallel']
        max_workers = args.workers or optimal_settings['max_workers']
        
        # 進捗トラッカー初期化
        progress_tracker = None
        if not args.no_progress:
            progress_tracker = ProgressTracker(len(image_files), logger)
        
        extracted_texts = []
        
        if use_parallel and len(image_files) > 1:
            logger.info(f"並列処理モード開始: {max_workers}ワーカー")
            
            # 進捗コールバック関数
            def progress_callback(completed, item_name, processing_time):
                if progress_tracker:
                    progress_tracker.update(completed, item_name, processing_time)
            
            # 並列OCR処理
            parallel_processor = ParallelOCRProcessor(logger, max_workers)
            results = parallel_processor.process_images_parallel(
                image_files, progress_callback, killer
            )
            
            # 結果を順序通りに並べる
            for index, text, confidence, proc_time in results:
                extracted_texts.append(text)
                processed_files.append(image_files[index])
                success_count += 1
                
                logger.log_page_processing(
                    index + 1, len(image_files), 
                    image_files[index].name, confidence
                )
            
            error_count = len(image_files) - len(results)
            
        else:
            logger.info("順次処理モード開始")
            
            # 順次処理（従来の方法）
            image_utils = ImageUtils(logger)
            ocr_processor = OCRProcessor()
            
            for i, image_path in enumerate(image_files, start_index + 1):
                # 各ページ処理前に停止チェック
                killer.check_and_exit(f"ページ {i} 処理開始前")
                
                item_start_time = time.time()
                
                try:
                    if progress_tracker:
                        progress_tracker.update(i, image_path.name)
                    
                    logger.log_page_processing(i, len(image_files) + start_index, image_path.name)
                    
                    # 画像ファイル検証
                    if not error_handler.validate_image_file(image_path):
                        logger.warning(f"画像ファイルをスキップ: {image_path}")
                        error_count += 1
                        continue
                    
                    # 画像前処理（リトライ付き）
                    @error_handler.retry_on_failure("画像前処理")
                    def process_image():
                        # 前処理前に停止チェック
                        killer.check_and_exit(f"ページ {i} 画像前処理")
                        processed_image = image_utils.preprocess_image(image_path)
                        if processed_image is None:
                            raise FileProcessError(f"画像前処理に失敗: {image_path}")
                        return processed_image
                    
                    processed_image = process_image()
                    
                    # OCR実行（リトライ付き）
                    @error_handler.retry_on_failure("OCR処理")
                    def extract_ocr_text():
                        # OCR実行前に停止チェック
                        killer.check_and_exit(f"ページ {i} OCR処理")
                        text = ocr_processor.extract_text(processed_image)
                        if not text.strip():
                            raise OCRError(f"テキスト抽出に失敗: {image_path}")
                        return text
                    
                    text = extract_ocr_text()
                    extracted_texts.append(text)
                    processed_files.append(image_path)
                    success_count += 1
                    
                    # 信頼度ログ
                    confidence = ocr_processor.get_confidence(processed_image)
                    item_processing_time = time.time() - item_start_time
                    
                    if progress_tracker:
                        progress_tracker.update(i, image_path.name, item_processing_time)
                    
                    logger.log_page_processing(i, len(image_files) + start_index, 
                                             image_path.name, confidence)
                    
                    # 定期的なチェックポイント作成
                    if i % 5 == 0:
                        error_handler.create_progress_checkpoint(
                            checkpoint_file, processed_files, i
                        )
                    
                except Exception as e:
                    error_count += 1
                    context = {
                        'ページ番号': i,
                        'ファイル名': str(image_path),
                        '書籍名': book_name
                    }
                    error_handler.logger.log_error_with_context(e, context)
                    
                    if progress_tracker:
                        progress_tracker.add_error(f"ページ {i}: {str(e)}")
                    
                    # クリティカルエラーでない場合は続行
                    if not isinstance(e, (KeyboardInterrupt, SystemExit)):
                        logger.warning(f"ページ {i} をスキップして続行")
                        continue
                    else:
                        raise
        
        # テキスト結合・保存
        if extracted_texts:
            combined_text = '\n\n'.join(extracted_texts)
            logger.info(f"テキスト結合完了: {len(extracted_texts)}ページ")
            
            # 直接的なファイル保存（詳細エラー確認用）
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(combined_text)
                
                logger.info(f"出力ファイル保存完了: {output_file}")
                logger.info(f"抽出テキスト文字数: {len(combined_text)}")
                
                # ファイル存在確認
                if output_file.exists():
                    file_size = output_file.stat().st_size
                    logger.info(f"出力ファイルサイズ: {file_size} bytes")
                else:
                    logger.error(f"出力ファイルが作成されていません: {output_file}")
                    error_count += 1
                    
            except Exception as e:
                import traceback
                logger.error(f"出力ファイル保存エラー: {e}")
                logger.error(f"詳細トレースバック: {traceback.format_exc()}")
                logger.error(f"出力ファイルパス: {output_file}")
                logger.error(f"テキスト長: {len(combined_text)}")
                error_count += 1
        else:
            logger.warning("抽出されたテキストがありません")
        
        # 進捗完了表示
        if progress_tracker:
            progress_tracker.complete()
        
        # 処理完了
        total_time = time.time() - start_time
        logger.log_processing_end(book_name, total_time, success_count, error_count)
        
        # チェックポイントファイル削除（正常完了時）
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logger.info("チェックポイントファイル削除")
        
    except KeyboardInterrupt:
        logger.warning("処理が中断されました（Ctrl+C）")
        logger.info("--resume オプションで処理を再開できます")
        
        # 部分的な結果を保存（可能であれば）
        if extracted_texts:
            try:
                partial_text = '\n\n'.join(extracted_texts)
                partial_file = Path('output') / f'{book_name}_partial.txt'
                with open(partial_file, 'w', encoding='utf-8') as f:
                    f.write(partial_text)
                logger.info(f"部分的な結果を保存しました: {partial_file}")
                logger.info(f"処理済みページ数: {len(extracted_texts)}")
            except Exception as e:
                logger.error(f"部分結果保存エラー: {e}")
        
        sys.exit(1)
        
    except Exception as e:
        total_time = time.time() - start_time
        context = {
            '処理時間': f"{total_time:.2f}秒",
            '成功ページ': success_count,
            'エラーページ': error_count,
            '書籍名': book_name
        }
        error_handler.logger.log_error_with_context(e, context)
        sys.exit(1)
        
    finally:
        # 最終統計
        error_handler.log_final_statistics()
        logger.info(f"ログファイル: {logger.get_log_file_path()}")


if __name__ == '__main__':
    main()