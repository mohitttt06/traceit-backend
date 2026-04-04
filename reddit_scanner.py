import requests
import time
import html
from hasher import generate_hash_from_url, compare_hashes
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "contentrace-scanner/1.0 (by /u/contentrace)"
}

SUBREDDITS = ["CricketControversial", "ipl", "IndianSports"]

def build_search_query(content_name):
    words = content_name.strip().split()
    query = "+".join(words[:4])
    return query

def extract_image_url(post_data):
    post_url = post_data.get("url", "")
    if any(post_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return post_url
    if "i.redd.it" in post_url or "i.imgur.com" in post_url:
        return post_url

    try:
        preview = post_data.get("preview", {})
        images = preview.get("images", [])
        if images:
            source = images[0].get("source", {})
            url = source.get("url", "")
            if url:
                return html.unescape(url)
    except Exception:
        pass

    try:
        media_metadata = post_data.get("media_metadata", {})
        if media_metadata:
            for item in media_metadata.values():
                if item.get("e") == "Image":
                    s = item.get("s", {})
                    url = s.get("u", "") or s.get("gif", "")
                    if url:
                        return html.unescape(url)
    except Exception:
        pass

    thumbnail = post_data.get("thumbnail", "")
    if thumbnail and thumbnail.startswith("http") and "thumbs.redditmedia" in thumbnail:
        return thumbnail

    return None


def scan_subreddit(subreddit, query, registered_hash):
    """Scan a single subreddit — runs in parallel thread"""
    matches = []
    print(f"Searching r/{subreddit} for '{query}'...")
    try:
        url = (
            f"https://www.reddit.com/r/{subreddit}/search.json"
            f"?q={query}&sort=new&limit=25&restrict_sr=1"
        )
        response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code == 429:
            print(f"Rate limited on r/{subreddit} — skipping")
            return matches  # Skip instead of blocking everything

        if response.status_code != 200:
            print(f"Could not reach r/{subreddit} — status {response.status_code}")
            return matches

        posts = response.json()["data"]["children"]
        print(f"Found {len(posts)} posts in r/{subreddit}")

        image_posts = 0
        for post in posts:
            data = post["data"]
            image_url = extract_image_url(data)
            if not image_url:
                continue

            image_posts += 1
            print(f"  Hashing: {image_url[:80]}...")

            post_hash = generate_hash_from_url(image_url)
            if not post_hash:
                continue

            distance, match_score = compare_hashes(registered_hash, post_hash)
            print(f"  Distance: {distance} | Score: {match_score}%")

            if distance <= 15:
                matches.append({
                    "source_url": f"https://reddit.com{data['permalink']}",
                    "post_title": data.get("title", "Unknown"),
                    "subreddit": subreddit,
                    "match_score": match_score,
                    "detection_method": "pHash" if distance <= 8 else "pHash-Near"
                })
                print(f"  *** MATCH found in r/{subreddit} — score {match_score}% ***")

        print(f"  {image_posts} image posts processed in r/{subreddit}")

    except Exception as e:
        print(f"Error scanning r/{subreddit}: {e}")

    return matches


def scan_reddit(registered_hash, content_name="sports"):
    matches = []
    query = build_search_query(content_name)
    print(f"Search query built: {query}")

    # Scan all subreddits in parallel
    with ThreadPoolExecutor(max_workers=len(SUBREDDITS)) as executor:
        futures = {
            executor.submit(scan_subreddit, subreddit, query, registered_hash): subreddit
            for subreddit in SUBREDDITS
        }
        for future in as_completed(futures):
            result = future.result()
            matches.extend(result)

    return matches