import subprocess

files = [
    "modules/douyin_fetcher.py",
    "modules/downloader.py",
    "modules/scheduler.py",
    "tests/test_douyin_api.py",
    "tests/test_downloader.py",
    "tests/test_douyin_fetcher.py"
]
res = subprocess.run(['git', 'diff', 'HEAD', '--'] + files, capture_output=True, text=True)
diff = res.stdout

added = 0
removed = 0
for line in diff.split("\n"):
    if line.startswith("+") and not line.startswith("+++"):
        added += 1
    elif line.startswith("-") and not line.startswith("---"):
        removed += 1

print(f"Stats: +{added} -{removed} changes.")
if len(diff) == 0:
    print("Diff is EMPTY.")
else:
    print("Diff generated.")
    with open("diff_output.txt", "w", encoding="utf-8") as f:
        f.write(diff)
