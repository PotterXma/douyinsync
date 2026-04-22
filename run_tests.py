import subprocess

with open('out.log', 'w', encoding='utf-8') as f:
    subprocess.run(['python', '-m', 'pytest', 'tests/', '--tb=short'], stdout=f, text=True)
