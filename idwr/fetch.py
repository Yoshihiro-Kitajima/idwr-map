"""Discover published links from official JIHS pages and fetch with retry/backoff."""
import re
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = 'https://id-info.jihs.go.jp/surveillance/idwr/provisional/'
ALLOWED_HOSTS = {'id-info.jihs.go.jp', 'idsc.nih.go.jp'}

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)

def trusted_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f'公式ドメイン以外への取得は許可しません: {url}')
    return url

def fetch(url):
    trusted_url(url)
    for attempt in range(3):
        try:
            request = Request(url, headers={'User-Agent': 'IDWR-Static-Dashboard/0.1 (+primary-data-visualization)'})
            with urlopen(request, timeout=35) as response:
                trusted_url(response.geturl())
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise ValueError('公開データの想定サイズを超えています')
                return raw
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError('unreachable')

def discover_year(year):
    index_url = f'{BASE}{year}/index.html'
    text = fetch(index_url).decode('utf-8-sig')
    parser = Links(); parser.feed(text)
    found = {}
    for href in parser.links:
        url = urljoin(index_url, href)
        match = re.search(rf'/provisional/{year}/(\d{{1,2}})/(?:index\.html)?$', url)
        if match:
            week = int(match[1])
            if not 1 <= week <= 53:
                raise ValueError('不正な週リンク')
            found[week] = trusted_url(url)
    if not found:
        raise ValueError(f'{year}年の公開週リンクが見つかりません')
    return found

def discover_csv(page_url, year, week):
    text = fetch(page_url).decode('utf-8-sig')
    parser = Links(); parser.feed(text)
    expected = f'{year}-{week:02d}-teiten.csv'
    links = {trusted_url(urljoin(page_url, href)) for href in parser.links if urlparse(href).path.endswith('/' + expected) or href == expected}
    if len(links) != 1:
        raise ValueError(f'定点週次CSVを一意に特定できません: {page_url}')
    # The publication date is distinct from the CSV compilation date.
    match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\s*第\s*' + str(week) + r'週', text)
    published_on = '-'.join([match[1], match[2].zfill(2), match[3].zfill(2)]) if match else None
    return links.pop(), published_on
