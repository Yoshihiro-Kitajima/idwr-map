"""Strict parser for the JIHS weekly sentinel CSV, not cumulative tables."""
import csv
import hashlib
import io
import math
import re
import unicodedata
from datetime import date, timedelta

PREFECTURES = [
    '北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県',
    '茨城県','栃木県','群馬県','埼玉県','千葉県','東京都','神奈川県',
    '新潟県','富山県','石川県','福井県','山梨県','長野県','岐阜県',
    '静岡県','愛知県','三重県','滋賀県','京都府','大阪府','兵庫県',
    '奈良県','和歌山県','鳥取県','島根県','岡山県','広島県','山口県',
    '徳島県','香川県','愛媛県','高知県','福岡県','佐賀県','長崎県',
    '熊本県','大分県','宮崎県','鹿児島県','沖縄県',
]
MISSING = {'', '-', '−', 'ー', '―', '—', '－'}

class SourceFormatError(ValueError):
    pass

def normalize(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text)).strip()

def decode_csv(raw):
    for encoding in ('utf-8-sig', 'cp932', 'shift_jis'):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    raise SourceFormatError('CSVの文字コードを判定できません')

def number(token, *, integer=False):
    token = token.strip()
    if token in MISSING:
        return None
    value = unicodedata.normalize('NFKC', token).replace(',', '')
    if not re.fullmatch(r'\d+(?:\.\d+)?', value):
        raise SourceFormatError(f'想定外の数値表記: {token!r}')
    result = float(value)
    if not math.isfinite(result) or result < 0 or (integer and not result.is_integer()):
        raise SourceFormatError(f'不正な数値: {token!r}')
    return int(result) if integer else result

def disease_id(name):
    label = normalize(name)
    if label == 'インフルエンザ':
        return 'influenza'
    if label == 'COVID-19':
        return 'covid19'
    return 'd-' + hashlib.sha256(label.encode()).hexdigest()[:12]

def parse_week(raw, year, week):
    text, encoding = decode_csv(raw)
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 52 or '定点' not in ''.join(rows[0]):
        raise SourceFormatError('定点の週次CSVではありません')
    title = normalize(''.join(rows[1]))
    match = re.search(r'(\d{4})年(\d{1,2})週\((\d{2})月(\d{2})日[～~](\d{2})月(\d{2})日\)', title)
    if not match or tuple(map(int, match.group(1, 2))) != (year, week):
        raise SourceFormatError('CSV内の年・週が取得対象と一致しません')
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    if tuple(map(int, match.group(3, 4, 5, 6))) != (monday.month, monday.day, sunday.month, sunday.day):
        raise SourceFormatError('CSVの対象期間が報告週対応と一致しません')
    created_match = re.search(r'(\d{4})年(\d{2})月(\d{2})日作成', title)
    created_on = '-'.join(created_match.groups()) if created_match else None
    header_idx = next((i for i in range(2, min(8, len(rows))) if len(rows[i]) > 2 and normalize(rows[i][1]) == '報告' and normalize(rows[i][2]) == '定当'), None)
    if header_idx is None:
        raise SourceFormatError('「報告」「定当」の列見出しがありません')
    names = rows[header_idx - 1]
    columns = rows[header_idx]
    if len(columns) % 2 != 1:
        raise SourceFormatError('疾患ごとの2列構成が変わっています')
    diseases = []
    for i in range(1, len(columns), 2):
        if normalize(columns[i]) != '報告' or normalize(columns[i + 1]) != '定当':
            raise SourceFormatError(f'列 {i} の報告/定当ペアが不正です')
        name = normalize(names[i])
        if not name or (i + 1 < len(names) and names[i + 1].strip()):
            raise SourceFormatError('疾患名の列構成が不正です')
        diseases.append({'id': disease_id(name), 'name': name, 'source_name': names[i]})
    if len(set(d['id'] for d in diseases)) != len(diseases):
        raise SourceFormatError('疾患名が重複しています')
    by_name = {}
    for row in rows[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue
        name = normalize(row[0])
        if name not in ['総数', *PREFECTURES]:
            raise SourceFormatError(f'想定外の集計行: {name}')
        if name in by_name or len(row) != len(columns):
            raise SourceFormatError(f'重複または列不足: {name}')
        by_name[name] = row
    if set(by_name) != set(['総数', *PREFECTURES]):
        raise SourceFormatError('総数と47都道府県が揃っていません')
    data = {}
    for i, disease in enumerate(diseases):
        count_col = 1 + 2 * i
        source_rows = [by_name[n] for n in ['総数', *PREFECTURES]]
        data[disease['id']] = {
            'reports': [number(r[count_col], integer=True) for r in source_rows],
            'rates': [number(r[count_col + 1]) for r in source_rows],
            # Preserve the original missing/dash notation; numeric 0.00 remains zero.
            'report_marks': [r[count_col].strip() if number(r[count_col], integer=True) is None else None for r in source_rows],
            'rate_marks': [r[count_col + 1].strip() if number(r[count_col + 1]) is None else None for r in source_rows],
        }
    return {
        'year': year, 'week': week, 'start': monday.isoformat(), 'end': sunday.isoformat(),
        'source_created_on': created_on, 'encoding': encoding, 'diseases': data,
    }, diseases
