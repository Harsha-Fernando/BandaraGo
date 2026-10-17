"""Local HTTP evidence; does not measure browser paint or third-party map tiles."""
import argparse
import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, build_opener

parser = argparse.ArgumentParser()
parser.add_argument('--base-url', default='http://127.0.0.1:8000')
parser.add_argument('--users', type=int, default=10)
parser.add_argument('--iterations', type=int, default=5)
args = parser.parse_args()


def visitor(index):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    results = []
    def request(path, data=None):
        started = time.perf_counter()
        encoded = urlencode(data).encode() if data is not None else None
        try:
            with opener.open(args.base_url + path, encoded, timeout=10) as response:
                body = response.read().decode()
                status = response.status
        except Exception as error:
            body = str(error); status = 0
        results.append({'path': path, 'method': 'POST' if data is not None else 'GET',
                        'status': status, 'seconds': round(time.perf_counter() - started, 4)})
        return body
    for _ in range(args.iterations):
        request('/attractions/')
        detail = request('/attractions/richmond-castle/')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', detail)
        add = re.search(r'action="(/planner/add/\d+/)"', detail)
        if not token or not add:
            results.append({'path': 'parse-add-form', 'method': 'GET', 'status': 0, 'seconds': 0})
            continue
        plan = request(add.group(1), {'csrfmiddlewaretoken': token.group(1)})
        if 'Richmond Castle' not in plan:
            results.append({'path': 'verify-session-write', 'method': 'GET', 'status': 0, 'seconds': 0})
        confirmation = request('/planner/clear/confirm/')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', confirmation)
        if token:
            request('/planner/clear/', {'csrfmiddlewaretoken': token.group(1), 'confirmed': 'yes'})
    return results

baseline = visitor(0)
started = time.perf_counter()
with ThreadPoolExecutor(max_workers=args.users) as pool:
    results = [row for rows in pool.map(visitor, range(args.users)) for row in rows]
elapsed = time.perf_counter() - started
listing = [row['seconds'] for row in results if row['path'] == '/attractions/']
ordered = sorted(row['seconds'] for row in results)
print(json.dumps({
    'environment': 'Local Django development server and PostgreSQL; no network throttling; excludes browser rendering and map tiles',
    'users': args.users, 'iterations_each': args.iterations, 'requests': len(results),
    'errors': sum(row['status'] != 200 for row in results), 'elapsed_seconds': round(elapsed, 4),
    'baseline_listing_mean_seconds': round(statistics.mean(row['seconds'] for row in baseline if row['path'] == '/attractions/'), 4),
    'concurrent_listing_mean_seconds': round(statistics.mean(listing), 4),
    'concurrent_listing_max_seconds': max(listing),
    'all_requests_p95_seconds': ordered[max(0, int(len(ordered) * .95) - 1)],
    'all_requests_max_seconds': max(ordered), 'results': results,
}, indent=2))
