import os, re, base64, json, requests

GH_TOKEN = os.environ['GH_TOKEN']
OWNER = 'MariavHeland'
REPO = 'godostuff'
HEADERS = {'Authorization': f'token {GH_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}

# The old EntryGate background pattern to find and replace
# We look for the style on the EntryGate outer div
OLD_BG_PATTERN = re.compile(
    r"(const EntryGate=\(\{onAccept\}\)=>\(\s*<div style=\{\{)minHeight:.*?background:[^,]+,[^}]+\}\}",
    re.DOTALL
)

# Actually use a simpler targeted replacement:
# Find the EntryGate div style background and replace with beige
# The current pattern is: background:"linear-gradient(180deg,rgba(10,8,30,...
OLD_ENTRY_BG = re.compile(
    r'(const EntryGate=\(\{onAccept\}\)=>\(\s*<div style=\{\{minHeight:"100vh",)background:"[^"]+"',
    re.DOTALL
)
NEW_ENTRY_BG = r'\1background:"linear-gradient(180deg,#F5EDD8 0%,#EDE0C8 100%)"'

def get_editions():
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/editions'
    r = requests.get(url, headers=HEADERS)
    return [item['name'] for item in r.json() if item['type'] == 'dir']

def get_file(path):
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}'
    r = requests.get(url, headers=HEADERS)
    data = r.json()
    content = base64.b64decode(data['content']).decode('utf-8')
    return content, data['sha']

def commit_file(path, content, sha, message):
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}'
    payload = {
        'message': message,
        'content': base64.b64encode(content.encode('utf-8')).decode('utf-8'),
        'sha': sha
    }
    r = requests.put(url, headers=HEADERS, json=payload)
    return r.status_code

editions = get_editions()
print(f'Found {len(editions)} editions')

updated = 0
skipped = 0
for city in sorted(editions):
    path = f'editions/{city}/index.html'
    try:
        content, sha = get_file(path)
    except Exception as e:
        print(f'  ERROR reading {city}: {e}')
        continue

    # Check if EntryGate already has beige background
    if 'background:"linear-gradient(180deg,#F5EDD8' in content:
        print(f'  SKIP {city} (already beige)')
        skipped += 1
        continue

    # Replace the EntryGate background
    new_content = OLD_ENTRY_BG.sub(NEW_ENTRY_BG, content)

    if new_content == content:
        # Try alternate pattern - maybe the bg uses different syntax
        # Look for the EntryGate component specifically
        # Pattern: minHeight:"100vh",background:"linear-gradient(180deg,rgba(
        alt_old = re.compile(
            r'(minHeight:"100vh",background:)"linear-gradient\(180deg,rgba\([^"]+\)"'
        )
        new_content = alt_old.sub(
            r'\1"linear-gradient(180deg,#F5EDD8 0%,#EDE0C8 100%)"',
            content, count=1  # only replace the FIRST occurrence (EntryGate)
        )

    if new_content == content:
        print(f'  NO_MATCH {city}')
        skipped += 1
        continue

    status = commit_file(path, new_content, sha, f'style: beige EntryGate background for {city}')
    if status in (200, 201):
        print(f'  UPDATED {city}')
        updated += 1
    else:
        print(f'  FAIL {city} status={status}')

print(f'Done: {updated} updated, {skipped} skipped')
