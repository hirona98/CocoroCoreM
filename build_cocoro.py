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

    # ビルドディレクトリをクリーンアップ（jre/neo4jは保護）
    build_path = Path("build")
    if build_path.exists():
        shutil.rmtree(build_path)
        print(f"🗑️ build ディレクトリをクリーンアップしました")
    
    # distディレクトリは選択的にクリーンアップ
    dist_path = Path("dist")
    if dist_path.exists():
        app_dist_path = dist_path / app_name
        if app_dist_path.exists():
            # jreとneo4jを一時的に退避
            temp_jre = None
            temp_neo4j = None
            
            jre_path = app_dist_path / "jre"
            neo4j_path = app_dist_path / "neo4j"
            
            if jre_path.exists():
                temp_jre = Path("temp_jre_backup")
                if temp_jre.exists():
                    shutil.rmtree(temp_jre)
                shutil.move(str(jre_path), str(temp_jre))
                print(f"💾 jreディレクトリを一時退避しました")
                
            if neo4j_path.exists():
                temp_neo4j = Path("temp_neo4j_backup")
                if temp_neo4j.exists():
                    shutil.rmtree(temp_neo4j)
                shutil.move(str(neo4j_path), str(temp_neo4j))
                print(f"💾 neo4jディレクトリを一時退避しました")
            
            # distディレクトリをクリーンアップ
            shutil.rmtree(dist_path)
            print(f"🗑️ dist ディレクトリをクリーンアップしました")
            
            # 退避したディレクトリを後で復元するためのフラグを設定
            if temp_jre or temp_neo4j:
                build_config["_temp_jre"] = temp_jre
                build_config["_temp_neo4j"] = temp_neo4j
        else:
            shutil.rmtree(dist_path)
            print(f"🗑️ dist ディレクトリをクリーンアップしました")

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
        
        # neo4jとjreを配布ディレクトリに復元・コピー
        print("\n📦 重要ディレクトリの確認・復元・コピー中...")
        dist_dir = exe_path.parent
        
        # 退避したディレクトリの復元
        temp_jre = build_config.get("_temp_jre")
        temp_neo4j = build_config.get("_temp_neo4j")
        
        # jreディレクトリの処理
        jre_dest = dist_dir / "jre"
        if temp_jre and temp_jre.exists():
            shutil.move(str(temp_jre), str(jre_dest))
            print(f"🔄 jreディレクトリを復元しました: {jre_dest}")
        elif not jre_dest.exists():
            jre_src = Path("jre")
            if jre_src.exists():
                shutil.copytree(jre_src, jre_dest)
                print(f"✅ jreディレクトリをコピー: {jre_dest}")
            else:
                print("❌ jreディレクトリが見つかりません")
        else:
            print(f"⏭️ jreディレクトリは既に存在します: {jre_dest}")
        
        # neo4jディレクトリの処理
        neo4j_dest = dist_dir / "neo4j"
        if temp_neo4j and temp_neo4j.exists():
            shutil.move(str(temp_neo4j), str(neo4j_dest))
            print(f"🔄 neo4jディレクトリを復元しました: {neo4j_dest}")
        elif not neo4j_dest.exists():
            neo4j_src = Path("neo4j")
            if neo4j_src.exists():
                shutil.copytree(neo4j_src, neo4j_dest)
                print(f"✅ neo4jディレクトリをコピー: {neo4j_dest}")
            else:
                print("❌ neo4jディレクトリが見つかりません")
        else:
            print(f"⏭️ neo4jディレクトリは既に存在します: {neo4j_dest}")
        
        # 一時ファイルのクリーンアップ
        for temp_dir in [temp_jre, temp_neo4j]:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)
        
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
        
        # MemOS統合の注意事項を表示
        print("\n⚠️ MemOS統合配布に関する注意事項:")
        print("   - UTF-8モードでの実行推奨: python -X utf8")
        print("   - 初回起動時にMemOSの初期化が行われます")
        print("   - Neo4jとJREディレクトリが完全に含まれています")
        print("   - 設定ファイル（../UserDataM/setting.json）が必要です")
        print("   - インターネット接続が必要（OpenAI API呼び出し）")
        
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