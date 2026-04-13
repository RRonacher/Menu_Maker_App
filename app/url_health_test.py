import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.database import get_database

HEALTHY_STATUSES = {200, 403, 429}

def check_url(pk, url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def make_request(method):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, response.reason, None
        except urllib.error.HTTPError as e:
            return e.code, e.reason, None
        except urllib.error.URLError as e:
            return None, None, f"UNREACHABLE — {e.reason}"
        except Exception as e:
            return None, None, f"ERROR — {e}"

    status, reason, error = make_request("HEAD")

    # Fall back to GET if HEAD returns a 5xx — some servers don't support HEAD
    if status is not None and 500 <= status < 600:
        status, reason, error = make_request("GET")

    if error:
        return pk, url, None, error
    elif status in HEALTHY_STATUSES:
        return pk, url, status, f"OK — {status} {reason}"
    else:
        return pk, url, status, f"BROKEN — {status} {reason}"

def run_health_check():
    db = get_database()
    print("DB connection successful, fetching recipes...")
    recipe_df = db.get_recipes_df()

    tasks = [
        (row["PK"], row["url"])
        for _, row in recipe_df.iterrows()
        if isinstance(row["url"], str) and row["url"].strip()
    ]

    print(f"Checking {len(tasks)} URLs across 10 threads...\n")
    flagged = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_url, pk, url): (pk, url) for pk, url in tasks}
        for future in as_completed(futures):
            pk, url, status, message = future.result()
            print(f"{message} — PK:{pk} — {url}")
            if not message.startswith("OK"):
                flagged.append({"pk": pk, "url": url, "status": status, "reason": message})

    print(f"\n--- Done --- Checked: {len(tasks)} | Flagged: {len(flagged)}")
    return len(tasks), flagged


# Keep the file runnable directly from the command line too
if __name__ == "__main__":
    run_health_check()