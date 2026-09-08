import os
import sys
import json
import time
import requests
import hashlib
import subprocess
from pathlib import Path

LANG_EXT = {
    'cpp': 'cpp',
    'c++': 'cpp',
    'python': 'py',
    'python3': 'py',
    'java': 'java',
    'c': 'c',
    'csharp': 'cs',
    'javascript': 'js',
    'typescript': 'ts',
    'ruby': 'rb',
    'swift': 'swift',
    'golang': 'go',
    'go': 'go',
    'scala': 'scala',
    'kotlin': 'kt',
    'rust': 'rs',
    'php': 'php',
    'sql': 'sql',
    'mysql': 'sql',
    'oracle': 'sql',
    'pythondata': 'py',
    'elixir': 'ex',
    'dart': 'dart'
}

def get_session_cookie():
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        return sys.argv[1]
    cookie_env = os.environ.get('LEETCODE_SESSION')
    if cookie_env:
        return cookie_env
    cookie_file = Path('leetcode_cookie.txt')
    if cookie_file.exists():
        return cookie_file.read_text().strip()
    return None

def fetch_all_authenticated_submissions(session_cookie, csrf_token=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://leetcode.com/submissions/',
        'Cookie': f'LEETCODE_SESSION={session_cookie}' + (f'; csrftoken={csrf_token}' if csrf_token else '')
    }
    if csrf_token:
        headers['X-CSRFToken'] = csrf_token

    all_submissions = []
    offset = 0
    limit = 100
    has_next = True

    print("Fetching submissions using authenticated API...", flush=True)
    while has_next:
        url = f"https://leetcode.com/api/submissions/?offset={offset}&limit={limit}"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"Error fetching submissions at offset {offset}: HTTP {r.status_code}", flush=True)
                break
            data = r.json()
            dump = data.get('submissions_dump', [])
            if not dump:
                break
            all_submissions.extend(dump)
            print(f"Fetched {len(dump)} submissions (total so far: {len(all_submissions)})", flush=True)
            has_next = data.get('has_next', False)
            offset += limit
            time.sleep(0.3)
        except Exception as e:
            print(f"Exception while fetching submissions: {e}", flush=True)
            break

    return all_submissions

def fetch_recent_public_submissions(username='eishantbansal1323'):
    url = "https://leetcode.com/graphql"
    query = """
    query recentSubmissions($username: String!, $limit: Int!) {
      recentSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
        statusDisplay
        lang
      }
    }
    """
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.post(url, json={'query': query, 'variables': {'username': username, 'limit': 100}}, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get('data', {}).get('recentSubmissionList', [])
    except Exception as e:
        print(f"Error fetching public submissions: {e}", flush=True)
    return []

_qdetails_cache = {}

def fetch_question_details(title_slug):
    if title_slug in _qdetails_cache:
        return _qdetails_cache[title_slug]
    url = "https://leetcode.com/graphql"
    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionId
        questionFrontendId
        title
        titleSlug
        content
        difficulty
        topicTags {
          name
          slug
        }
      }
    }
    """
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.post(url, json={'query': query, 'variables': {'titleSlug': title_slug}}, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            res = data.get('data', {}).get('question', {})
            _qdetails_cache[title_slug] = res
            return res
    except Exception as e:
        print(f"Error fetching question details for {title_slug}: {e}", flush=True)
    return {}

def format_frontend_id(frontend_id):
    try:
        num = int(frontend_id)
        return f"{num:04d}"
    except (ValueError, TypeError):
        return str(frontend_id).zfill(4)

def git_hash_file(filepath):
    if not os.path.exists(filepath):
        return ""
    with open(filepath, 'rb') as f:
        data = f.read()
    header = f"blob {len(data)}\0".encode('utf-8')
    return hashlib.sha1(header + data).hexdigest()

def main():
    repo_dir = Path(__file__).parent.resolve()
    os.chdir(repo_dir)

    session_cookie = get_session_cookie()
    csrf_token = os.environ.get('LEETCODE_CSRFTOKEN')

    submissions = []
    if session_cookie:
        submissions = fetch_all_authenticated_submissions(session_cookie, csrf_token)
    else:
        print("No LEETCODE_SESSION cookie provided. Attempting public recent submissions...", flush=True)
        submissions = fetch_recent_public_submissions('eishantbansal1323')

    if not submissions:
        print("No submissions retrieved.", flush=True)
        if not session_cookie:
            print("\nIMPORTANT: Please provide your LEETCODE_SESSION cookie to retrieve all past code submissions!", flush=True)
            print("Usage: python sync_leetcode.py <YOUR_LEETCODE_SESSION_COOKIE>", flush=True)
        return

    print(f"\nTotal raw submissions retrieved: {len(submissions)}", flush=True)

    # Filter for Accepted submissions
    accepted_submissions = [s for s in submissions if s.get('status_display') == 'Accepted' or s.get('statusDisplay') == 'Accepted']
    print(f"Accepted submissions: {len(accepted_submissions)}", flush=True)

    # Group by title_slug, selecting latest accepted submission
    latest_per_problem = {}
    for sub in accepted_submissions:
        slug = sub.get('title_slug') or sub.get('titleSlug')
        if not slug:
            continue
        ts = int(sub.get('timestamp', 0))
        if slug not in latest_per_problem or ts > latest_per_problem[slug]['ts']:
            latest_per_problem[slug] = {
                'submission': sub,
                'ts': ts
            }

    print(f"Unique solved problems found in retrieved submissions: {len(latest_per_problem)}", flush=True)

    # Load existing stats.json if exists
    stats_file = Path('stats.json')
    stats = {"leetcode": {"easy": 0, "medium": 0, "hard": 0, "shas": {}, "solved": 0}}
    if stats_file.exists():
        try:
            stats = json.loads(stats_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    shas = stats["leetcode"].get("shas", {})
    topic_map = {}
    difficulty_counts = {"Easy": 0, "Medium": 0, "Hard": 0}

    # Process each problem
    processed_count = 0
    for slug, info in latest_per_problem.items():
        sub = info['submission']
        qdetails = fetch_question_details(slug)
        if not qdetails:
            print(f"Skipping {slug}, details unavailable", flush=True)
            continue

        raw_fid = qdetails.get('questionFrontendId') or qdetails.get('questionId', '0')
        fid = format_frontend_id(raw_fid)
        title = qdetails.get('title', slug)
        difficulty = qdetails.get('difficulty', 'Easy')
        content = qdetails.get('content', '')
        tags = qdetails.get('topicTags', [])

        difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1

        folder_name = f"{fid}-{slug}"
        folder_path = repo_dir / folder_name
        folder_path.mkdir(exist_ok=True)

        lang_raw = sub.get('lang', 'cpp').lower()
        ext = LANG_EXT.get(lang_raw, 'cpp')
        code_file_name = f"{folder_name}.{ext}"
        code_path = folder_path / code_file_name
        readme_path = folder_path / 'README.md'

        # Get code if available
        code_content = sub.get('code')
        if not code_content:
            if code_path.exists():
                code_content = code_path.read_text(encoding='utf-8')
            else:
                code_content = f"// Code for {title} ({lang_raw})\n"

        code_path.write_text(code_content, encoding='utf-8')

        # Generate problem README.md
        problem_url = f"https://leetcode.com/problems/{slug}"
        problem_readme_content = f"<h2><a href=\"{problem_url}\">{raw_fid}. {title}</a></h2><h3>{difficulty}</h3><hr>{content}\n"
        readme_path.write_text(problem_readme_content, encoding='utf-8')

        # Track git SHAs in stats.json
        code_sha = git_hash_file(code_path)
        readme_sha = git_hash_file(readme_path)

        if folder_name not in shas:
            shas[folder_name] = {}
        shas[folder_name][code_file_name] = code_sha
        shas[folder_name]['README.md'] = readme_sha
        shas[folder_name]['difficulty'] = difficulty.lower()

        # Track topic tags
        for tag in tags:
            tag_name = tag.get('name')
            if tag_name:
                if tag_name not in topic_map:
                    topic_map[tag_name] = set()
                topic_map[tag_name].add(folder_name)

        processed_count += 1
        print(f"[{processed_count}/{len(latest_per_problem)}] Synced: {folder_name}", flush=True)

    # Collect existing folders for topic mapping as well
    for item in repo_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            parts = item.name.split('-', 1)
            if len(parts) == 2 and parts[0].isdigit():
                slug = parts[1]
                qdetails = fetch_question_details(slug)
                if qdetails:
                    tags = qdetails.get('topicTags', [])
                    for tag in tags:
                        tag_name = tag.get('name')
                        if tag_name:
                            if tag_name not in topic_map:
                                topic_map[tag_name] = set()
                            topic_map[tag_name].add(item.name)

    # Rebuild root README.md
    root_readme_path = repo_dir / 'README.md'
    readme_lines = [
        "A collection of LeetCode questions to ace the coding interview! - Created using [LeetHub v2](https://github.com/arunbhardwaj/LeetHub-2.0)",
        "<!---LeetCode Topics Start-->",
        "# LeetCode Topics"
    ]

    for topic in sorted(topic_map.keys()):
        readme_lines.append(f"## {topic}")
        readme_lines.append("|  |")
        readme_lines.append("| ------- |")
        for fname in sorted(topic_map[topic]):
            readme_lines.append(f"| [{fname}](https://github.com/eishant2313/leetcode/tree/master/{fname}) |")

    readme_lines.append("<!---LeetCode Topics End-->")
    root_readme_path.write_text("\n".join(readme_lines) + "\n", encoding='utf-8')

    # Update stats.json
    all_solved = len([k for k in shas if k not in ['README.md', 'stats.json']])
    stats["leetcode"]["easy"] = sum(1 for v in shas.values() if isinstance(v, dict) and v.get('difficulty') == 'easy')
    stats["leetcode"]["medium"] = sum(1 for v in shas.values() if isinstance(v, dict) and v.get('difficulty') == 'medium')
    stats["leetcode"]["hard"] = sum(1 for v in shas.values() if isinstance(v, dict) and v.get('difficulty') == 'hard')
    stats["leetcode"]["solved"] = all_solved
    stats["leetcode"]["shas"] = shas
    stats["leetcode"]["shas"]["README.md"] = {"": git_hash_file(root_readme_path)}
    stats["leetcode"]["shas"]["stats.json"] = {"": ""}

    stats_file.write_text(json.dumps(stats, indent=2), encoding='utf-8')

    print("\nSummary of sync:", flush=True)
    print(f"Total solved problems tracked in repository: {all_solved}", flush=True)
    print(f"Easy: {stats['leetcode']['easy']}, Medium: {stats['leetcode']['medium']}, Hard: {stats['leetcode']['hard']}", flush=True)

    # Git commit and push
    try:
        subprocess.run(["git", "add", "."], check=True)
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout
        if status.strip():
            print("\nCommitting changes to git...", flush=True)
            subprocess.run(["git", "commit", "-m", "Sync LeetCode submissions [LeetHub v2]"], check=True)
            print("Pushing to GitHub...", flush=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("Successfully pushed to https://github.com/eishant2313/leetcode!", flush=True)
        else:
            print("\nRepository working tree clean. Nothing to commit.", flush=True)
    except Exception as e:
        print(f"Git operation failed: {e}", flush=True)

if __name__ == '__main__':
    main()
