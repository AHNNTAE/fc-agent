from pathlib import Path

path = Path(__file__).parent / ".env"
print(".env 위치:", path)
print("파일 있음:", path.exists())

if path.exists():
    raw = path.read_bytes()
    print("BOM 있음:", raw.startswith(b"\xef\xbb\xbf"))
    for i, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if "=" in line:
            name, value = line.split("=", 1)
            print(f"{i}번째 줄: 이름=[{name}] / 값 길이={len(value.strip())}")
        else:
            print(f"{i}번째 줄: (= 없음) [{line[:20]}]")