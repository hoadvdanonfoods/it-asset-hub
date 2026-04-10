import sys
import os
sys.path.append(os.getcwd())
os.environ["DATABASE_URL"] = "sqlite:///./test_temp.db"

from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    client = TestClient(app)

    print("CHECK 1: GET /assets works")
    resp_get = client.get("/assets/")
    print("GET /assets status:", resp_get.status_code)
    
    print("\nCHECK 2: POST /assets/bulk-archive with 2 IDs works")
    resp_archive = client.post("/assets/bulk-archive", data={"asset_ids": "1,2", "confirm_text": "ARCHIVE"}, follow_redirects=False)
    print("POST /assets/bulk-archive status:", resp_archive.status_code)
    print("POST Location:", resp_archive.headers.get("location"))

    print("\nCHECK 3: wrong confirm text is rejected gracefully")
    resp_bad = client.post("/assets/bulk-archive", data={"asset_ids": "1,2", "confirm_text": "WRONG"}, follow_redirects=False)
    print("POST wrong confirm status:", resp_bad.status_code)
    print("POST bad Location:", resp_bad.headers.get("location"))

    print("\nCHECK 4: single retire/restore still works")
    resp_single_retire = client.post("/assets/0/retire", follow_redirects=False)
    print("POST /assets/0/retire status:", resp_single_retire.status_code)
    resp_single_restore = client.post("/assets/0/restore", follow_redirects=False)
    print("POST /assets/0/restore status:", resp_single_restore.status_code)

if __name__ == "__main__":
    run_tests()
