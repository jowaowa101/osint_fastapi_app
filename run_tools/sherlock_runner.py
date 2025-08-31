import subprocess
import os
import re

def run_sherlock(username: str) -> dict:
    sherlock_path = "/Users/apple/Desktop/osint-llm-tool/tools/sherlock-master/sherlock_project/sherlock.py"

    try:
        result = subprocess.run(
            ['python3', sherlock_path, username],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output_text = result.stdout if result.returncode == 0 else result.stderr

        # 🧼 Clean output: extract all URLs from `[+] Site: URL` lines
        matches = re.findall(r'\[\+\] .*?: (https?://[^\s]+)', output_text)
        return {
            "tool": "Sherlock",
            "username": username,
            "total_results": len(matches),
            "sites": matches
        }

    except Exception as e:
        return {
            "tool": "Sherlock",
            "username": username,
            "error": str(e)
        }
