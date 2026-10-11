"""Copy a validated, self-contained static site to dist/."""
from pathlib import Path
import json
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
def build(root=ROOT):
    source = root / 'public'
    data = json.loads((source / 'data/data.json').read_text(encoding='utf-8'))
    if data['schema_version'] != 1 or len(data['prefectures']) != 47:
        raise ValueError('公開データが不正です')
    svg = ET.parse(source / 'assets/japan.svg')
    codes = [e.get('data-code').zfill(2) for e in svg.getroot().iter() if e.get('data-code')]
    if set(codes) != {f'{i:02d}' for i in range(1, 48)} or len(codes) != 47:
        raise ValueError('地図と47都道府県の対応が不正です')
    dest = root / 'dist'
    dest.mkdir(exist_ok=True)
    shutil.copytree(source, dest, dirs_exist_ok=True)
    print(f'静的サイトを生成: {dest}')
if __name__ == '__main__':
    build()
