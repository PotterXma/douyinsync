import subprocess
import os

diff = subprocess.check_output(['git', 'diff', 'HEAD'], encoding='utf8')
spec = open('_bmad-output/implementation-artifacts/1-5-pipeline-coordinator-assembly.md', encoding='utf-8').read()

bh_prompt = f"""# Blind Hunter Prompt
Please run the `@/bmad-review-adversarial-general` skill on the following diff:

```diff
{diff}
```
"""

eh_prompt = f"""# Edge Case Hunter Prompt
Please run the `@/bmad-review-edge-case-hunter` skill on the following diff. Note you have read access to the project to investigate beyond the diff if needed.

```diff
{diff}
```
"""

aa_prompt = f"""# Acceptance Auditor Prompt
You are an Acceptance Auditor. Review this diff against the spec and context docs. Check for: violations of acceptance criteria, deviations from spec intent, missing implementation of specified behavior, contradictions between spec constraints and actual code. Output findings as a Markdown list. Each finding: one-line title, which AC/constraint it violates, and evidence from the diff.

## Spec
{spec}

## Diff
```diff
{diff}
```
"""

with open('_bmad-output/implementation-artifacts/prompt-blind-hunter.md', 'w', encoding='utf8') as f:
    f.write(bh_prompt)
    
with open('_bmad-output/implementation-artifacts/prompt-edge-case-hunter.md', 'w', encoding='utf8') as f:
    f.write(eh_prompt)
    
with open('_bmad-output/implementation-artifacts/prompt-acceptance-auditor.md', 'w', encoding='utf8') as f:
    f.write(aa_prompt)
    
print("Generated prompt files.")
