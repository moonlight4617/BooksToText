#!/usr/bin/env python3
"""
Kindle Screenshot Capture Tool
Kindle Windows アプリから自動スクリーンショットを撮影
"""

import argparse
import sys
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent / 'src'))

from kindle_screenshot import KindleScreenshotCapture
from logger import Logger


def main():
    parser = argparse.ArgumentParser(
        description='Kindle書籍の自動スクリーンショットキャプチャ',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本使用（手動停止まで）
  python kindle_capture.py --book "技術書名"
  
  # ページ範囲指定
  python kindle_capture.py --book "技術書名" --start 10 --end 50
  
  # カスタム設定
  python kindle_capture.py --book "技術書名" --delay 3.0 --key space
  
注意事項:
  1. Kindleアプリを起動し、対象書籍を開いておいてください
  2. 緊急停止: マウスを画面左上角に移動
  3. 通常停止: Ctrl+C
  4. ページめくり速度に応じて --delay を調整してください
        """
    )
    
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
    parser.add_argument('--output-dir', 
                       help='出力ディレクトリ（デフォルト: input/[book_name]）')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='ログレベル（デフォルト: INFO）')
    
    args = parser.parse_args()
    
    # ログ初期化
    import logging
    logger = Logger(log_level=getattr(logging, args.log_level))
    
    # 開始メッセージ
    logger.info("=" * 60)
    logger.info("Kindle Screenshot Capture Tool")
    logger.info("=" * 60)
    logger.info(f"書籍名: {args.book}")
    logger.info(f"開始ページ: {args.start}")
    
    if args.end:
        logger.info(f"終了ページ: {args.end} (総 {args.end - args.start + 1} ページ)")
    else:
        logger.info("終了ページ: 手動停止まで")
    
    logger.info(f"ページめくり待機時間: {args.delay}秒")
    logger.info(f"ページめくりキー: {args.key}")
    
    # 出力ディレクトリ確認
    if args.output_dir:
        output_dir = Path(args.output_dir)
        logger.info(f"出力ディレクトリ: {output_dir}")
    else:
        output_dir = Path('input') / args.book
        logger.info(f"出力ディレクトリ: {output_dir} (自動設定)")
    
    # 事前確認
    print("\n準備確認:")
    print("1. Kindleアプリが起動していますか？")
    print("2. 対象の書籍が開かれていますか？")
    print("3. 開始ページが表示されていますか？")
    print("\n重要:")
    print("- 緊急停止: マウスを画面左上角に移動")
    print("- 通常停止: Ctrl+C")
    
    response = input("\n準備完了でキャプチャを開始しますか？ (y/N): ").strip().lower()
    
    if response not in ['y', 'yes']:
        logger.info("キャプチャをキャンセルしました")
        return
    
    try:
        # スクリーンショットキャプチャ実行
        capturer = KindleScreenshotCapture(logger)
        capturer.configure_settings(
            page_turn_delay=args.delay,
            page_turn_key=args.key
        )
        
        captured_count = capturer.capture_pages(
            book_name=args.book,
            start_page=args.start,
            end_page=args.end,
            output_dir=args.output_dir
        )
        
        # 結果表示
        logger.info("=" * 60)
        logger.info("キャプチャ完了")
        logger.info("=" * 60)
        logger.info(f"キャプチャしたページ数: {captured_count}")
        logger.info(f"保存先: {output_dir}")
        
        if captured_count > 0:
            logger.info("\n次のステップ:")
            logger.info(f"python src/main.py --book {args.book}")
            logger.info("でOCR処理を実行できます")
        
        # ログファイル場所を表示
        logger.info(f"\nログファイル: {logger.get_log_file_path()}")
        
    except KeyboardInterrupt:
        logger.warning("ユーザーによる中断")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()