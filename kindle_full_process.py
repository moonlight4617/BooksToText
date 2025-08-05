#!/usr/bin/env python3
"""
Kindle Full Process Tool
Kindle書籍の自動スクリーンショット撮影からOCR処理まで一括実行
"""

import argparse
import sys
import time
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent / 'src'))

from kindle_screenshot import KindleScreenshotCapture
from logger import Logger
from src.subprocess_manager import ManagedSubprocess
from src.signal_handler import GracefulKiller
import subprocess


def main():
    parser = argparse.ArgumentParser(
        description='Kindle書籍の完全自動処理（スクリーンショット + OCR）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本使用（手動停止まで）
  python kindle_full_process.py --book "技術書名"
  
  # ページ範囲指定 + 並列OCR
  python kindle_full_process.py --book "技術書名" --start 1 --end 100 --parallel
  
  # 高速設定
  python kindle_full_process.py --book "技術書名" --delay 1.5 --parallel --workers 4
  
処理ステップ:
  1. 自動スクリーンショット撮影
  2. OCR処理実行
  3. テキストファイル出力
        """
    )
    
    # スクリーンショット設定
    parser.add_argument('--book', required=True, 
                       help='書籍名（保存フォルダ名として使用）')
    parser.add_argument('--start', type=int, default=1, 
                       help='開始ページ番号（デフォルト: 1）')
    parser.add_argument('--end', type=int, 
                       help='終了ページ番号（未指定時は手動停止まで）')
    parser.add_argument('--delay', type=float, default=2.0, 
                       help='ページめくり後の待機時間（秒、デフォルト: 2.0）')
    parser.add_argument('--key', default='right', 
                       choices=['right', 'space', 'pagedown'], 
                       help='ページめくりキー（デフォルト: right）')
    
    # OCR設定
    parser.add_argument('--parallel', action='store_true', 
                       help='OCR並列処理を有効化（高速化）')
    parser.add_argument('--workers', type=int, default=None,
                       help='OCR並列処理ワーカー数（自動設定時はNone）')
    parser.add_argument('--no-progress', action='store_true',
                       help='進捗表示を無効化')
    
    # 共通設定
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='ログレベル（デフォルト: INFO）')
    parser.add_argument('--skip-screenshot', action='store_true',
                       help='スクリーンショット撮影をスキップしてOCRのみ実行')
    parser.add_argument('--yes', '-y', action='store_true',
                       help='確認プロンプトを自動でYesで回答')
    
    args = parser.parse_args()
    
    # ログ初期化
    import logging
    logger = Logger(log_level=getattr(logging, args.log_level))
    
    # シグナルハンドラー初期化
    killer = GracefulKiller(logger)
    
    # 処理開始
    logger.info("=" * 70)
    logger.info("Kindle Complete Processing Tool")
    logger.info("=" * 70)
    logger.info(f"書籍名: {args.book}")
    
    total_start_time = time.time()
    
    try:
        # ステップ1: スクリーンショット撮影
        if not args.skip_screenshot:
            logger.info("\n" + "=" * 30)
            logger.info("ステップ1: スクリーンショット撮影")
            logger.info("=" * 30)
            
            # 事前確認
            if not args.yes:
                print("\n準備確認:")
                print("1. Kindleアプリが起動していますか？")
                print("2. 対象の書籍が開かれていますか？")
                print("3. 開始ページが表示されていますか？")
                
                response = input("\n準備完了でスクリーンショットを開始しますか？ (y/N): ").strip().lower()
                
                if response not in ['y', 'yes']:
                    logger.info("処理をキャンセルしました")
                    return
            else:
                logger.info("自動実行モード: 確認プロンプトをスキップ")
            
            # スクリーンショット実行
            capturer = KindleScreenshotCapture(logger)
            capturer.configure_settings(
                page_turn_delay=args.delay,
                page_turn_key=args.key
            )
            
            screenshot_start_time = time.time()
            captured_count = capturer.capture_pages(
                book_name=args.book,
                start_page=args.start,
                end_page=args.end
            )
            screenshot_time = time.time() - screenshot_start_time
            
            if captured_count == 0:
                logger.error("スクリーンショット撮影に失敗しました")
                return
            
            logger.info(f"スクリーンショット完了: {captured_count}ページ ({screenshot_time:.1f}秒)")
            
            # OCR前の待機
            logger.info("3秒後にOCR処理を開始します...")
            time.sleep(3)
        
        else:
            logger.info("スクリーンショット撮影をスキップします")
        
        # ステップ2: OCR処理
        logger.info("\n" + "=" * 30)
        logger.info("ステップ2: OCR処理")
        logger.info("=" * 30)
        
        # OCRコマンド構築
        ocr_cmd = [
            sys.executable, 'src/main.py',
            '--book', args.book,
            '--log-level', args.log_level
        ]
        
        if args.parallel:
            ocr_cmd.append('--parallel')
        
        if args.workers:
            ocr_cmd.extend(['--workers', str(args.workers)])
        
        if args.no_progress:
            ocr_cmd.append('--no-progress')
        
        logger.info(f"OCRコマンド実行: {' '.join(ocr_cmd)}")
        
        # OCR処理実行（キャンセル可能）
        ocr_start_time = time.time()
        subprocess_manager = ManagedSubprocess(logger)
        
        returncode = subprocess_manager.run_with_cancellation(
            ocr_cmd, 
            killer=killer,
            timeout=3600  # 1時間タイムアウト
        )
        
        ocr_time = time.time() - ocr_start_time
        
        if returncode is None:
            logger.warning("OCR処理が中断されました")
            return
        elif returncode != 0:
            logger.error(f"OCR処理に失敗しました (リターンコード: {returncode})")
            return
        
        logger.info(f"OCR処理完了 ({ocr_time:.1f}秒)")
        
        # ステップ3: 完了報告
        total_time = time.time() - total_start_time
        
        logger.info("\n" + "=" * 70)
        logger.info("全処理完了")
        logger.info("=" * 70)
        
        if not args.skip_screenshot:
            logger.info(f"スクリーンショット: {captured_count}ページ ({screenshot_time:.1f}秒)")
        
        logger.info(f"OCR処理時間: {ocr_time:.1f}秒")
        logger.info(f"総処理時間: {total_time:.1f}秒")
        
        # 出力ファイル確認
        output_file = Path('output') / f'{args.book}.txt'
        if output_file.exists():
            file_size = output_file.stat().st_size
            logger.info(f"出力ファイル: {output_file} ({file_size} bytes)")
            
            # 文字数概算
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    char_count = len(f.read())
                logger.info(f"抽出文字数: 約{char_count:,}文字")
            except:
                pass
        
        logger.info(f"\nログファイル: {logger.get_log_file_path()}")
        
        print("\n🎉 Kindle書籍のテキスト化が完了しました！")
        print(f"📄 結果ファイル: {output_file}")
        print("📝 NotebookLMや他のAIツールでご活用ください")
        
    except KeyboardInterrupt:
        logger.warning("ユーザーによる中断")
        
        # 部分的な結果を確認
        output_file = Path('output') / f'{args.book}.txt'
        if output_file.exists():
            file_size = output_file.stat().st_size
            logger.info(f"部分的な結果ファイル: {output_file} ({file_size} bytes)")
        
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()