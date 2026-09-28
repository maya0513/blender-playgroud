"""One output layout shared by build, validation, rendering and the CLI."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / 'hamamachi_breakwater.blend'
REVIEW = ROOT / 'review'
IMAGES = REVIEW / 'images'
REPORTS = REVIEW / 'reports'
LOGS = REVIEW / 'logs'
RENDERS = ROOT / 'renders'
FINAL_IMAGE = RENDERS / 'hamamachi_breakwater.png'
CAMERAS = {
    'photo': 'Photo camera',
    'clay': 'Photo camera',
    'overview': 'Overview camera',
    'shelter': 'Shelter inspection camera',
    'ferry': 'Ferry inspection camera',
    'reverse': 'Reverse inspection camera',
    'pavilion': 'Pavilion inspection camera',
    'walk': 'Walk camera',
}

REVIEW_INDEX = """# 現行モデルの確認資料

- 確認画像：[全体](images/overview.png)・[屋根](images/shelter.png)・[フェリー](images/ferry.png)・[逆方向](images/reverse.png)・[建物](images/pavilion.png)・[目線](images/walk.png)・[写真視点](images/photo.png)・[形状](images/clay.png)
- 完成画像：[3024×3024px](../renders/hamamachi_breakwater.png)
- 検証：[構造](reports/validation.json)・[接続](reports/contacts.json)・[外観](reports/appearance.json)・[成果物](reports/verification.json)
- 描画設定と時間：[確認画像](reports/preview.json)・[完成画像](reports/final.json)

`images/` は視点名、`reports/` と `logs/` は処理名で固定します。
同じ処理の再実行は同じ場所を更新し、日付・連番・final2などの派生名を増やしません。
画像は一時ファイルへの描画が成功した後に置換します。失敗時の既存画像は保持されるため、最新性は画像だけで判断せず `verify_outputs.py` のシーンハッシュ検査で確認します。
`build.json` / `build.log` はシーン再構築時に生成します。ログは `run.py` が管理します。
この索引は `scripts/project.py` から生成されます。
"""

def ensure_directories():
    for path in (IMAGES, REPORTS, LOGS, RENDERS):
        path.mkdir(parents=True, exist_ok=True)
    (REVIEW / 'README.md').write_text(REVIEW_INDEX)

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_report(name, value):
    ensure_directories()
    target = REPORTS / (name + '.json')
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(target)
