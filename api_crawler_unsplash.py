import os
import sys
import json
import csv
import time
import math
import requests as req
from pathlib import Path
from collections import Counter

API_URL = "https://api.unsplash.com/search/photos"
ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")


QUERIES = ["architecture", "art", "design", "drawing", "heritage", "illustration", "painting", "pattern", "portrait", "sculpture"]
PER_PAGE = 30
CONTENT_FILTER = "high"

MAX_REQUESTS_PER_HOUR = 50
QUOTA_USAGE_RATIO = 0.9
USABLE_REQUESTS = int(MAX_REQUESTS_PER_HOUR * QUOTA_USAGE_RATIO)
WINDOW_SECONDS = 3600

TARGET_TOTAL = USABLE_REQUESTS * PER_PAGE
MIN_ROWS = 500
AUTO_WAIT = False
MAX_RETRIES = 2
REQUEST_TIMEOUT = 30

RESERVED_REQUESTS = MAX_REQUESTS_PER_HOUR - USABLE_REQUESTS
IMAGE_DELAY = 0.2
REQUESTS_PER_RUN = min(USABLE_REQUESTS, math.ceil(TARGET_TOTAL / PER_PAGE))

class QuotaExceeded(Exception): """Đã hết (hoặc sắp hết) quota 50 request/giờ"""
class FetchError(Exception): """Gọi API thất bại sau khi đã retry"""


# Đường dẫn lưu dữ liệu
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"
CSV_PATH = DATA_DIR / "unsplash_metadata.csv"
STATE_PATH = DATA_DIR / "crawl_state.json"
OLD_PER_PAGE = 30

CSV_COLUMNS = [
    "image_id",
    "query_label",
    "description",
    "alt_description",
    "created_at",
    "likes",
    "width",
    "height",
    "color",
    "user_name",
    "user_url",
]


# Theo dõi quota và số request đã thực hiện
class Quota:
    def __init__(self):
        self.reset()

    def reset(self):
        self.used = 0
        self.remaining = None
        self.window_start = None

    def mark_request(self):
        if self.window_start is None:
            self.window_start = time.time()
        self.used += 1

    def update(self, headers):
        try:
            self.remaining = int(headers.get("X-Ratelimit-Remaining"))
        except (TypeError, ValueError):
            pass

    def exhausted(self):
        if self.used >= USABLE_REQUESTS:
            return True
        if self.remaining is not None and self.remaining <= RESERVED_REQUESTS:
            return True
        return False

    def seconds_to_reset(self):
        start = self.window_start or time.time()
        return max(0.0, start + WINDOW_SECONDS + 5 - time.time())


# Hàm phụ
def safe_name(text):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text.strip())

def next_pages(offsets, limit):
    pos = dict(offsets)
    todo = []
    for _ in range(limit):
        q = min(QUERIES, key = lambda x: pos[x])
        todo.append((q, pos[q] // PER_PAGE + 1))
        pos[q] += PER_PAGE
    return todo

def load_state():
    """Trả về {query: số kết quả search đã cào}. Tự chuyển đổi state cũ (done_pages)."""
    offsets = {q: 0 for q in QUERIES}
    if not STATE_PATH.exists():
        return offsets
    try:
        data = json.loads(STATE_PATH.read_text(encoding = "utf-8"))
    except (json.JSONDecodeError, OSError):
        return offsets
 
    if "offsets" in data:
        for q, v in data["offsets"].items():
            if q in offsets:
                offsets[q] = int(v)
    elif "done_pages" in data:  # định dạng cũ: các page liên tiếp từ 1
        pages = {}
        for key in data["done_pages"]:
            q, pg = key.rsplit("|", 1)
            pages.setdefault(q, set()).add(int(pg))
        for q, ps in pages.items():
            n = 0
            while n + 1 in ps:
                n += 1
            if q in offsets:
                offsets[q] = n * OLD_PER_PAGE
    return offsets
 
def save_state(offsets):
    STATE_PATH.write_text(
        json.dumps({"offsets": offsets}, ensure_ascii = False, indent = 2),
        encoding = "utf-8",
    )

def load_existing():
    seen, counts = set(), Counter()
    if CSV_PATH.exists():
        with open(CSV_PATH, newline = "", encoding = "utf-8-sig") as f:
            for row in csv.DictReader(f):
                seen.add(row["image_id"])
                counts[row["query_label"]] += 1
    return seen, counts

def build_row(image, query):
    user = image.get("user") or {}
    return {
        "image_id": image["id"],
        "query_label": query,
        "description": image.get("description") or "",
        "alt_description": image.get("alt_description") or "",
        "created_at": image.get("created_at") or "",
        "likes": image.get("likes", 0),
        "width": image.get("width", ""),
        "height": image.get("height", ""),
        "color": image.get("color") or "",
        "user_name": user.get("name") or "",
        "user_url": (user.get("links") or {}).get("html") or "",
    }


# Gọi API Unsplash và tải ảnh
def fetch_page(session, query, page, quota):
    params = {
        "query": query,
        "page": page,
        "per_page": PER_PAGE,
        "content_filter": CONTENT_FILTER,
    }
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        if quota.exhausted():
            raise QuotaExceeded()
        quota.mark_request()
        try:
            resp = session.get(API_URL, params = params, timeout = REQUEST_TIMEOUT)
        except req.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt)
            continue

        quota.update(resp.headers)

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            sys.exit("ACCESS_KEY không hợp lệ (401). Kiểm tra biến môi trường UNSPLASH_ACCESS_KEY.")
        if resp.status_code in (403, 429):
            raise QuotaExceeded()
        if resp.status_code >= 500:
            last_err = f"HTTP {resp.status_code}"
            time.sleep(2 ** attempt)
            continue
        raise FetchError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    raise FetchError(f"{query} page {page} thất bại sau {MAX_RETRIES + 1} lần thử: {last_err}")


def download_image(session, url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True

    tmp = dest.with_suffix(".part")
    for attempt in range(MAX_RETRIES + 1):
        try:
            with session.get(url, stream = True, timeout = REQUEST_TIMEOUT) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size = 65536):
                        f.write(chunk)
            tmp.replace(dest)
            return True
        except (req.RequestException, OSError):
            time.sleep(2 ** attempt)

    if tmp.exists():
        tmp.unlink()
    return False


def main():
    if not ACCESS_KEY:
        sys.exit("Thiếu UNSPLASH_ACCESS_KEY")

    DATA_DIR.mkdir(exist_ok=True)
    for q in QUERIES:
        (DATA_DIR / safe_name(q)).mkdir(exist_ok=True)

    api = req.Session()
    api.headers.update({"Authorization": f"Client-ID {ACCESS_KEY}", "Accept-Version": "v1"})
    cdn = req.Session()
    cdn.headers.update({"User-Agent": "unsplash-dataset-crawler/1.0"})

    offsets = load_state()
    seen, counts = load_existing()
    quota = Quota()
    blocked = set()
    run_new = 0

    todo = next_pages(offsets, REQUESTS_PER_RUN)
    print(f"Lần chạy này: {len(todo)} request x {PER_PAGE} ảnh | "
          f"đã có {len(seen)} ảnh trong CSV")

    is_new_file = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
    stopped_early = False

    with open(CSV_PATH, "a", newline = "", encoding = "utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames = CSV_COLUMNS)
        if is_new_file:
            writer.writeheader()

        for i, (query, page) in enumerate(todo, 1):
            data = None
            while True:
                try:
                    data = fetch_page(api, query, page, quota)
                    break
                except QuotaExceeded:
                    if not AUTO_WAIT:
                        stopped_early = True
                        break
                    wait = quota.seconds_to_reset()
                    print(f"  Hết quota, chờ {wait / 60:.1f} phút rồi cào tiếp...")
                    time.sleep(wait)
                    quota.reset()
                except FetchError as e:
                    print(f"  ! Bỏ qua: {e}")
                    break

            if stopped_early:
                print("Dừng vì hết quota (AUTO_WAIT = False). Chạy lại script sau <= 1 giờ để cào tiếp.")
                break
            if data is None:
                continue

            all_ok = True
            new_rows = 0
            for photo in data.get("results", []):
                pid = photo["id"]
                if pid in seen:
                    continue
                dest = DATA_DIR / safe_name(query) / f"{pid}.jpg"
                if download_image(cdn, photo["urls"]["regular"], dest):
                    writer.writerow(build_row(photo, query))
                    seen.add(pid)
                    counts[query] += 1
                    new_rows += 1
                else:
                    all_ok = False
                    print(f"  ! Không tải được ảnh {pid}")
                time.sleep(IMAGE_DELAY)
            f.flush()

            if all_ok:
                offsets[query] = page * PER_PAGE
                save_state(offsets)
            else:
                blocked.add(query)

            print(f"[{i}/{len(todo)}] {query} - page {page}: +{new_rows} ảnh mới "
                  f"| quota API còn: {quota.remaining if quota.remaining is not None else '?'}")

    total = sum(counts.values())
    print("=" * 50)
    for q in QUERIES:
        print(f"  {q:<14} {counts[q]:>5} ảnh")
    print(f"Tổng: {total} ảnh | CSV: {CSV_PATH}")
    if total < MIN_ROWS:
        print(f"Mới có {total}/{MIN_ROWS} dòng -> chạy lại script sau <= 1 giờ để lấy thêm")
 

if __name__ == "__main__":
    main()
