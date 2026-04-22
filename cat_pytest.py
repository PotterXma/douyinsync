import sys
content = open('pytest_scheduler.txt', 'r', encoding='utf-16le').read()
lines = content.split('\n')
for i, l in enumerate(lines):
    if "ERRORS ===" in l or "FAILURES ===" in l or "Traceback (" in l:
        print("\n".join(lines[max(0, i-2):i+40]))
        break
