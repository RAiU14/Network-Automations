import re
import logging
import os
import json

def env_collector():
    directory_path = r"C:\Users\girish.n\Downloads\logs"
    output_json_path = os.path.join(directory_path, "env_results.json")

    # Regex covers both "show environment all" and "show environment"
    pattern_1_2 = (
        r"(-{5,}\s*show environment(?:\s+all)?\s*-{5,}[\s\S]*?-{5,}\s*show)"
    )
    pattern_3 = (
        r"(?mi)"  # m: ^/$ are line-based, i: case-insensitive
        r"(^[^\r\n#]*#\s*"                 # prompt line (anything up to '#')
        r"(?:sh[a-z]*)\s+"                 # 'sh' + >=0 letters (>=2 total letters)
        r"(?:env[a-z]*)"                   # 'env' + >=0 letters (>=3 total letters)
        r"(?:\s+al[a-z]*)?\s*$"            # optional 'al' + >=0 letters (>=2 total)
        r"[\r\n]+"                         # newline(s) after the command
        r"[\s\S]*?"                        # the body, non-greedy
        r"^[^\r\n#]*#\s*(?:sh[a-z]*)\b.*$)"# next prompt line that begins a 'sh...' command (e.g., '#show switch')
    )

    results = {}  # filename -> list of matched blocks

    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if not os.path.isfile(file_path):
            continue

        with open(file_path, "r", errors="ignore") as f:
            log_data = f.read()

        matches_1 = re.findall(pattern_1_2, log_data, re.IGNORECASE)
        matches_2 = re.findall(pattern_3, log_data)
        if matches_1:
            results[filename] = [m.strip() for m in matches_1]
            print(f"✅ Found {len(matches_1)} section(s) in {filename}")
        elif matches_2:
            results[filename] = [m.strip() for m in matches_2]
            print(f"✅ Found {len(matches_2)} section(s) in {filename}")
        else:
            print(f"⚠️ No matching sections in {filename}")

        # Save all results to JSON
        output_json_path = os.path.join(directory_path, "env_results.json")
        missing_json_path = os.path.join(directory_path, "env_results_missing.json")

        # 1) Save found (existing behavior)
        with open(output_json_path, "w", encoding="utf-8") as json_file:
            json.dump(results, json_file, indent=2, ensure_ascii=False)

        # 2) Build and save missing/empty
        processed_files = [
            f for f in os.listdir(directory_path)
            if os.path.isfile(os.path.join(directory_path, f))
        ]
        missing = {
            fname: []
            for fname in processed_files
            if fname not in results or not results.get(fname)  # also catches empty lists
        }

        with open(missing_json_path, "w", encoding="utf-8") as json_file:
            json.dump(missing, json_file, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: {output_json_path}")

if __name__ == '__main__':
    env_collector()