#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CocoroCoreM ビルドスクリプト - CocoroCoreと同じ方法"""

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
    "app_name": "CocoroCoreM",
    "icon_path": None,
    "onefile": False,
    "console": True,
}


def build_cocoro(config=None):
    """CocoroCoreMのWindowsバイナリをビルドする関数（CocoroCoreスタイル）"""
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
        spec_file = "CocoroCoreM.spec"

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
    build_path = Path("build")
    if build_path.exists():
        shutil.rmtree(build_path)
        print(f"🗑️ build ディレクトリをクリーンアップしました")
    
    # distディレクトリをクリーンアップ
    dist_path = Path("dist")
    if dist_path.exists():
        shutil.rmtree(dist_path)
        print(f"🗑️ dist ディレクトリをクリーンアップしました")

    # PyInstallerでスペックファイルを使用してビルド
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
        
        # neo4jとjreを配布ディレクトリにコピー
        print("\n📦 重要ディレクトリのコピー中...")
        dist_dir = exe_path.parent
        
        # jreディレクトリの処理
        jre_dest = dist_dir / "jre"
        jre_src = Path("jre")
        if jre_src.exists():
            shutil.copytree(jre_src, jre_dest)
            print(f"✅ jreディレクトリをコピー: {jre_dest}")
        else:
            print("❌ jreディレクトリが見つかりません")
        
        # neo4jディレクトリの処理
        neo4j_dest = dist_dir / "neo4j"
        neo4j_src = Path("neo4j")
        if neo4j_src.exists():
            shutil.copytree(neo4j_src, neo4j_dest)
            print(f"✅ neo4jディレクトリをコピー: {neo4j_dest}")
        else:
            print("❌ neo4jディレクトリが見つかりません")
        
        # 結果確認
        print(f"\n🔍 配布ディレクトリ構成確認:")
        for item in dist_dir.iterdir():
            if item.is_file():
                size = item.stat().st_size / (1024 * 1024)
                print(f"   📄 {item.name} ({size:.1f} MB)")
            elif item.is_dir():
                if item.name in ["neo4j", "jre"]:
                    file_count = len(list(item.rglob("*")))
                    print(f"   📁 {item.name}/ ({file_count} ファイル) ⭐重要")
                else:
                    file_count = len(list(item.rglob("*")))
                    print(f"   📁 {item.name}/ ({file_count} ファイル)")
        return True
    else:
        print("\n❌ ビルドに失敗しました。")
        print("実行ファイルが生成されませんでした。")
        return False


def main():
    """メイン関数"""
    print("CocoroCoreM - MemOS統合バックエンド ビルドツール")
    print("=" * 50)
    
    try:
        success = build_cocoro()
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