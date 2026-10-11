import csv
import io
import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from idwr.parser import SourceFormatError, decode_csv, parse_week
from idwr.update import ROOT, run

RAW = ROOT / 'tests/fixtures/2026-39-teiten.csv'

class ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = RAW.read_bytes()
        cls.record, cls.catalog = parse_week(cls.raw, 2026, 39)
    def modified(self, edit):
        text, _ = decode_csv(self.raw)
        rows = list(csv.reader(io.StringIO(text)))
        edit(rows)
        buffer = io.StringIO(); csv.writer(buffer).writerows(rows)
        return buffer.getvalue().encode('utf-8-sig')
    def test_actual_primary_csv_known_values(self):
        values = self.record['diseases']['influenza']
        self.assertEqual(values['rates'][0], 7.17)
        self.assertEqual(values['reports'][0], 26678)
        self.assertEqual(values['rates'][1], 4.52)
        self.assertEqual(values['rates'][47], 42.50)
        self.assertEqual(self.record['start'], '2026-09-21')
        self.assertEqual(len(self.catalog), 19)
    def test_all_published_json_matches_original_csv_and_hash(self):
        data = json.loads((ROOT / 'public/data/data.json').read_text(encoding='utf-8'))
        for key, record in data['weeks'].items():
            raw = (ROOT / record['source']['raw_path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record['source']['sha256'], key)
            year, week = map(int, key.split('-'))
            parsed, _ = parse_week(raw, year, week)
            self.assertEqual(parsed['diseases'], record['diseases'], key)
    def test_wrong_source_week_rejected(self):
        with self.assertRaises(SourceFormatError): parse_week(self.raw, 2026, 38)
    def test_zero_and_dash_are_distinct(self):
        raw = self.modified(lambda rows: rows[5].__setitem__(2, '0.00'))
        record, _ = parse_week(raw, 2026, 39)
        self.assertEqual(record['diseases']['influenza']['rates'][1], 0)
        raw = self.modified(lambda rows: rows[5].__setitem__(2, '-'))
        record, _ = parse_week(raw, 2026, 39)
        self.assertIsNone(record['diseases']['influenza']['rates'][1])
        self.assertEqual(record['diseases']['influenza']['rate_marks'][1], '-')
    def test_utf8_and_shiftjis_read_identically(self):
        record, _ = parse_week(self.modified(lambda rows: None), 2026, 39)
        self.assertEqual(record['diseases'], self.record['diseases'])
    def test_missing_prefecture_and_column_shift_rejected(self):
        with self.assertRaises(SourceFormatError):
            parse_week(self.modified(lambda rows: rows.pop(5)), 2026, 39)
        with self.assertRaises(SourceFormatError):
            parse_week(self.modified(lambda rows: rows[5].pop(2)), 2026, 39)
    def test_row_order_does_not_change_prefecture_alignment(self):
        def swap(rows): rows[5], rows[51] = rows[51], rows[5]
        record, _ = parse_week(self.modified(swap), 2026, 39)
        self.assertEqual(record['diseases'], self.record['diseases'])
    def test_unexpected_marker_rejected(self):
        with self.assertRaises(SourceFormatError):
            parse_week(self.modified(lambda rows: rows[5].__setitem__(2, '未確認')), 2026, 39)
    def test_fractional_report_count_rejected(self):
        with self.assertRaises(SourceFormatError):
            parse_week(self.modified(lambda rows: rows[5].__setitem__(1, '1.5')), 2026, 39)
    def test_failed_update_does_not_destroy_published_json(self):
        cache = ROOT / '.cache'; cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as folder:
            root = Path(folder)
            published = root / 'public/data/data.json'; published.parent.mkdir(parents=True)
            published.write_text('{"previous":"valid"}')
            with patch('idwr.update.discover_year', return_value={39:'https://id-info.jihs.go.jp/week'}), patch('idwr.update.discover_csv', return_value=('https://id-info.jihs.go.jp/data.csv',None)), patch('idwr.update.fetch', return_value=b'<html>not a CSV</html>'):
                with self.assertRaises(SourceFormatError): run([2026], pause=0, root=root)
            self.assertEqual(json.loads(published.read_text()), {'previous':'valid'})

if __name__ == '__main__': unittest.main()
