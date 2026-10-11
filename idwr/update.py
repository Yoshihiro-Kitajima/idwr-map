"""Fetch, validate and atomically publish data.json. Failed runs leave public JSON intact."""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .fetch import discover_year, discover_csv, fetch
from .parser import PREFECTURES, parse_week

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)

def run(years, refresh_weeks=12, pause=0.15, root=ROOT):
    raw_dir = root / 'data' / 'raw'
    metadata_path = root / 'data' / 'source-index.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    all_links = []
    for year in years:
        all_links.extend((year, week, page) for week, page in discover_year(year).items())
        time.sleep(pause)
    all_links.sort()
    refresh_keys = {(y, w) for y, w, _ in all_links[-refresh_weeks:]}
    weeks = {}; disease_catalog = {}
    # Include cached older years in the output when new years are added.
    for key, info in metadata.items():
        path = root / info['raw_path']
        if path.exists():
            year, week = map(int, key.split('-'))
            record, catalog = parse_week(path.read_bytes(), year, week)
            record['source'] = info
            weeks[key] = record
            disease_catalog.update({d['id']: d for d in catalog})
    for year, week, page in all_links:
        key = f'{year}-{week:02d}'
        raw_path = raw_dir / str(year) / f'{key}-teiten.csv'
        if raw_path.exists() and key in metadata and (year, week) not in refresh_keys:
            continue
        csv_url, published_on = discover_csv(page, year, week)
        time.sleep(pause)
        raw = fetch(csv_url)
        retrieved_at = datetime.now(JST).isoformat(timespec='seconds')
        record, catalog = parse_week(raw, year, week)
        info = {
            'page_url': page, 'csv_url': csv_url, 'retrieved_at': retrieved_at,
            'published_on': published_on, 'sha256': hashlib.sha256(raw).hexdigest(),
            'raw_path': raw_path.relative_to(root).as_posix(), 'provisional': True,
        }
        record['source'] = info
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
        metadata[key] = info
        weeks[key] = record
        disease_catalog.update({d['id']: d for d in catalog})
        print(f'{key}: {len(catalog)}疾患 × 47都道府県', flush=True)
        time.sleep(pause)
    if not weeks:
        raise ValueError('有効な週次データがありません')
    ordered = dict(sorted(weeks.items()))
    now = datetime.now(JST).isoformat(timespec='seconds')
    output = {
        'schema_version': 1, 'generated_at': now, 'last_checked_at': now,
        'publisher': '国立健康危機管理研究機構（JIHS）',
        'source_home': 'https://id-info.jihs.go.jp/surveillance/idwr/provisional/index.html',
        'provisional': True, 'latest': max(ordered),
        'prefectures': [{'code': f'{i:02d}', 'name': n, 'index': i} for i, n in enumerate(PREFECTURES, 1)],
        'diseases': list(disease_catalog.values()), 'weeks': ordered,
        'comparison_breaks': [{'week': '2025-15', 'reason': '2025年第15週から定点制度・定点数に変更があるため、変更前後の単純比較に注意が必要です。', 'source_url': 'https://id-info.jihs.go.jp/surveillance/idwr/idwr/2025/idwr2025-29.pdf'}],
    }
    # All source records must carry provenance, and arrays must align to JIS prefecture codes.
    for key, record in ordered.items():
        if not record['source']['csv_url'] or not record['source']['retrieved_at']:
            raise ValueError(f'出典メタデータが不足: {key}')
        for disease in record['diseases'].values():
            if any(len(disease[k]) != 48 for k in ['reports','rates','report_marks','rate_marks']):
                raise ValueError(f'都道府県配列の不整合: {key}')
    write_json(metadata_path, metadata)
    # Single atomic rename protects the deployed dataset against partial fetch/parse failures.
    write_json(root / 'public' / 'data' / 'data.json', output)
    print(f'完了: {len(ordered)}週・{len(disease_catalog)}疾患 / 最新 {output["latest"]}')
    return output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--years', nargs='+', type=int)
    parser.add_argument('--start-year', type=int, default=2025)
    parser.add_argument('--refresh-weeks', type=int, default=12)
    parser.add_argument('--pause', type=float, default=0.15)
    args = parser.parse_args()
    years = args.years or list(range(args.start_year, datetime.now(JST).year + 1))
    if args.refresh_weeks < 1 or args.pause < 0 or not years:
        parser.error('取得年・再取得週数・待機時間が不正です')
    run(years, args.refresh_weeks, args.pause)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'更新失敗（公開JSONは置き換えていません）: {exc}', file=sys.stderr)
        raise SystemExit(1)
