import urllib.request
import zipfile
import io
import os

url = 'https://asset.antigravityskills.com/skills/uiux-designer/uiux-designer-antigravityskills-com.zip'
print("Downloading...")
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        print("Extracting...")
        with zipfile.ZipFile(io.BytesIO(response.read())) as z:
            z.extractall('.agent/skills/')
    print("Done!")
except Exception as e:
    print(f"Error: {e}")
