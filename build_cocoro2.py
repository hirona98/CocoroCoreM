#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CocoroCore2 ビルドスクリプト - CocoroCoreと同じ方法"""

import shutil
import subprocess
import sys
from pathlib import Path
import io

# Windows環境でのUTF-8出力対応
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ビルド設定（CocoroCoreスタイル）
BUILD_CONFIG = {
    "app_name": "CocoroCore2",
    "icon_path": None,
    "onefile": False,
    "console": True,
}


def build_cocoro2(config=None):
    """CocoroCore2のWindowsバイナリをビルドする関数（CocoroCoreスタイル）"""
    build_config = config or BUILD_CONFIG
    app_name = build_config["app_name"]

    print(f"\n=== {app_name} ビルドを開始します ===")

    # 動的スペックファイル生成（CocoroCoreと同じ）
    print("📋 動的スペックファイルを生成中...")
    try:
        from create_spec import create_spec_file
        spec_file = create_spec_file()
        print(f"✅ スペックファイル生成完了: {spec_file}")
    except Exception as e:
        print(f"❌ スペックファイル生成に失敗: {e}")
        print("既存のスペックファイルを使用します")
        spec_file = "CocoroCore2.spec"

    # PyInstallerのインストール確認
    try:
        import importlib.util
        if importlib.util.find_spec("PyInstaller") is None:
            raise ImportError("PyInstaller is not installed")
        print("✅ PyInstallerは既にインストールされています")
    except ImportError:
        print("📦 PyInstallerをインストールしています...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "pyinstaller"],
                check=True,
                capture_output=True,
                text=True,
            )
            print("✅ PyInstallerのインストールが完了しました")
        except subprocess.SubprocessError as e:
            print(f"❌ PyInstallerのインストールに失敗しました: {e}")
            sys.exit(1)

    # ビルドディレクトリをクリーンアップ
    for dir_name in ["dist", "build"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"🗑️ {dir_name} ディレクトリをクリーンアップしました")

    # PyInstallerでスペックファイルを使用してビルド（CocoroCoreと同じ）
    print(f"\n📋 PyInstallerでビルド中（{spec_file}使用）...")
    spec_args = ["pyinstaller", spec_file, "--clean"]
    print("📋 実行するコマンド:", " ".join(spec_args))
    
    try:
        result = subprocess.call(spec_args)
        if result == 0:
            print("✅ PyInstallerの実行が完了しました")
        else:
            print(f"❌ PyInstallerがエラーコード {result} で終了しました")
            return False
    except Exception as e:
        print(f"❌ PyInstallerの実行に失敗しました: {e}")
        return False

    # 結果確認
    if build_config["onefile"]:
        exe_path = Path("dist") / f"{app_name}.exe"
    else:
        exe_path = Path("dist") / app_name / f"{app_name}.exe"
    
    if exe_path.exists():
        print(f"\n✨ ビルド成功！実行ファイル: {exe_path}")
        print(f"📁 配布用ディレクトリ: {exe_path.parent}")
        
        # ファイルサイズ確認
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"📊 実行ファイルサイズ: {size_mb:.1f} MB")
        
        # MemOS統合の注意事項を表示
        print("\n⚠️ MemOS統合に関する注意事項:")
        print("   - UTF-8モードでの実行推奨: python -X utf8")
        print("   - 初回起動時にMemOSの初期化が行われます")
        print("   - Neo4jとJREディレクトリが含まれています")
        print("   - 設定ファイル（UserData2/setting.json）が必要です")
        
        return True
    else:
        print("\n❌ ビルドに失敗しました。")
        print("実行ファイルが生成されませんでした。")
        return False


def main():
    """メイン関数"""
    print("CocoroCore2 - MemOS統合バックエンド ビルドツール")
    print("=" * 50)
    
    try:
        success = build_cocoro2()
        if success:
            print("\n🎉 ビルドが正常に完了しました！")
        else:
            print("\n💔 ビルドに失敗しました。")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ ユーザーによってビルドが中止されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()