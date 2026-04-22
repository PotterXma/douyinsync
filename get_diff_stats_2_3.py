import os
import subprocess

files_tracked = [
    "main.py", "modules/youtube_uploader.py", "modules/config_manager.py", 
    "modules/notifier.py", "modules/sweeper.py", "modules/downloader.py", 
    "modules/tray_app.py", "modules/win_ocr.py"
]
files_untracked = [
    "utils/sanitizer.py", "utils/logger.py", "tests/test_sanitizer.py"
]

diff_content = []

# Tracked files
try:
    cmd = ["git", "diff", "HEAD", "--"] + files_tracked
    out = subprocess.check_output(cmd, text=True, encoding='utf-8')
    diff_content.append(out)
except Exception as e:
    print(f"Error tracked: {e}")

# Untracked files
for f in files_untracked:
    try:
        # read the file
        if os.path.exists(f):
            with open(f, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                diff_content.append(f"--- /dev/null\n+++ b/{f}\n@@ -0,0 +1,{len(lines)} @@\n" + "".join(["+" + line for line in lines]))
    except Exception as e:
        print(f"Error untracked {f}: {e}")

diff_str = "\n".join(diff_content)
with open("diff_2_3.txt", "w", encoding='utf-8') as f:
    f.write(diff_str)

added = diff_str.count('\n+') - diff_str.count('\n+++')
removed = diff_str.count('\n-') - diff_str.count('\n---')
print(f"Files changed: {len(files_tracked) + len(files_untracked)}")
print(f"Lines added: {added}")
print(f"Lines removed: {removed}")
print(f"Total diff lines: {len(diff_str.splitlines())}")
