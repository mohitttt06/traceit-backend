from PIL import Image
import imagehash
import requests
from io import BytesIO

def generate_hash(image_path):
    try:
        img = Image.open(image_path).convert("RGB")
        phash = imagehash.phash(img)
        return str(phash)
    except Exception as e:
        print(f"Error hashing local image: {e}")
        return None

def generate_hash_from_url(url):
    try:
        headers = {"User-Agent": "contentrace-scanner/1.0"}
        response = requests.get(url, timeout=10, headers=headers)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        phash = imagehash.phash(img)
        return str(phash)
    except Exception as e:
        print(f"Could not hash image from URL {url}: {e}")
        return None

def compare_hashes(hash1, hash2):
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        distance = h1 - h2
        match_score = max(0, 100 - (distance * 3))
        return int(distance), int(match_score)
    except Exception as e:
        print(f"Error comparing hashes: {e}")
        return 999, 0