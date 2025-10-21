import requests

URL = "http://192.168.16.34/values.json"

response = requests.get(URL, auth=("admin", "1234"))  # uprav podle potřeby

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}\n")
print("Raw response:")
print("-" * 40)
print(response.text[:1000])  # vypíše prvních 1000 znaků
print("-" * 40)


def add(a, b):
    return a + b


# zkusíme bezpečně dekódovat JSON
try:
    data = response.json()
    print("✅ Parsed JSON:")
    print(data)
except Exception as e:
    print(f"⚠️ JSON decode failed: {e}")
