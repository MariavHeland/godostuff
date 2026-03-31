import os, re, json, base64, time, requests, warnings
warnings.filterwarnings('ignore')

GH_TOKEN = os.environ['GH_TOKEN']
PPLX_KEY = os.environ['PPLX_API_KEY']
REPO = 'MariavHeland/godostuff'
GH_API = 'https://api.github.com'
PPLX_URL = 'https://api.perplexity.ai/chat/completions'

CITIES = [
    {'slug':'coimbra','name':'Coimbra','country':'Portugal','lang':'Portuguese'},
    {'slug':'dusseldorf','name':'Duesseldorf','country':'Germany','lang':'German'},
    {'slug':'erfurt','name':'Erfurt','country':'Germany','lang':'German'},
    {'slug':'ghent','name':'Ghent','country':'Belgium','lang':'Dutch'},
    {'slug':'glasgow','name':'Glasgow','country':'Scotland','lang':'English'},
    {'slug':'hamburg','name':'Hamburg','country':'Germany','lang':'German'},
    {'slug':'hannover','name':'Hannover','country':'Germany','lang':'German'},
    {'slug':'helsinki','name':'Helsinki','country':'Finland','lang':'Finnish'},
    {'slug':'kotor','name':'Kotor','country':'Montenegro','lang':'Montenegrin'},
    {'slug':'kyiv','name':'Kyiv','country':'Ukraine','lang':'Ukrainian'},
    {'slug':'ljubljana','name':'Ljubljana','country':'Slovenia','lang':'Slovenian'},
    {'slug':'london','name':'London','country':'UK','lang':'English'},
    {'slug':'lyon','name':'Lyon','country':'France','lang':'French'},
    {'slug':'malaga','name':'Malaga','country':'Spain','lang':'Spanish'},
    {'slug':'malmo','name':'Malmo','country':'Sweden','lang':'Swedish'},
    {'slug':'marseille','name':'Marseille','country':'France','lang':'French'},
    {'slug':'mostar','name':'Mostar','country':'Bosnia','lang':'Bosnian'},
    {'slug':'munich','name':'Munich','country':'Germany','lang':'German'},
    {'slug':'naples','name':'Naples','country':'Italy','lang':'Italian'},
    {'slug':'nicosia','name':'Nicosia','country':'Cyprus','lang':'Greek'},
    {'slug':'nuremberg','name':'Nuremberg','country':'Germany','lang':'German'},
    {'slug':'ohrid','name':'Ohrid','country':'North Macedonia','lang':'Macedonian'},
    {'slug':'oslo','name':'Oslo','country':'Norway','lang':'Norwegian'},
    {'slug':'palermo','name':'Palermo','country':'Italy','lang':'Italian'},
    {'slug':'paris','name':'Paris','country':'France','lang':'French'},
    {'slug':'poznan','name':'Poznan','country':'Poland','lang':'Polish'},
    {'slug':'rostock','name':'Rostock','country':'Germany','lang':'German'},
    {'slug':'valencia','name':'Valencia','country':'Spain','lang':'Spanish'},
    {'slug':'valletta','name':'Valletta','country':'Malta','lang':'Maltese'},
    {'slug':'weimar','name':'Weimar','country':'Germany','lang':'German'},
    {'slug':'wroclaw','name':'Wroclaw','country':'Poland','lang':'Polish'},
    {'slug':'dresden','name':'Dresden','country':'Germany','lang':'German'},
    {'slug':'brandenburg','name':'Brandenburg an der Havel','country':'Germany','lang':'German'},
]

def gh_get(path):
    r = requests.get(f'{GH_API}/repos/{REPO}/contents/{path}',
        headers={'Authorization':f'token {GH_TOKEN}','Accept':'application/vnd.github.v3+json'})
    return r.json()

def gh_put(path, content_b64, sha, msg):
    r = requests.put(f'{GH_API}/repos/{REPO}/contents/{path}',
        headers={'Authorization':f'token {GH_TOKEN}','Accept':'application/vnd.github.v3+json'},
        json={'message':msg,'content':content_b64,'sha':sha})
    return r.status_code, r.json()

def ask_pplx(prompt):
    headers = {'Authorization':f'Bearer {PPLX_KEY}','Content-Type':'application/json'}
    body = {
        'model':'sonar-pro',
        'messages':[{'role':'user','content':prompt}],
        'max_tokens':8000,
        'temperature':0.2
    }
    for attempt in range(3):
        try:
            r = requests.post(PPLX_URL, headers=headers, json=body, timeout=120)
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content']
            time.sleep(10)
        except Exception as e:
            print(f'  PPLX error: {e}')
            time.sleep(10)
    return None

def clean_json(text):
    text = re.sub(r'^```[\w]*\n?','',text.strip())
    text = re.sub(r'```$','',text.strip())
    m = re.search(r'(\[.*\])',text,re.DOTALL)
    if m: text = m.group(1)
    try: return json.loads(text)
    except:
        text = text.replace("\u2018","'").replace("\u2019","'")
        text = text.replace("\u201c",'"').replace("\u201d",'"')
        try: return json.loads(text)
        except: return None

def parse_places(html):
    m = re.search(r'const P\s*=\s*(\[.*?\]);',html,re.DOTALL)
    if not m: return [], ''
    raw = m.group(1)
    places = []
    for pm in re.finditer(r'\{[^{}]+\}',raw,re.DOTALL):
        try:
            obj_str = pm.group(0)
            obj_str = re.sub(r"'([^']*)':",r'"\1":',obj_str)
            obj_str = re.sub(r":\s*'([^']*)'(?=[,}])",lambda x: ': "' + x.group(1).replace('"',"'") + '"',obj_str)
            places.append(json.loads(obj_str))
        except: pass
    return places, raw

def enrich_city(city):
    slug = city['slug']
    name = city['name']
    country = city['country']
    lang = city['lang']
    print(f'\n--- {name} ---')
    
    api_resp = gh_get(f'editions/{slug}/index.html')
    if 'content' not in api_resp:
        print(f'  No file found for {slug}')
        return
    sha = api_resp['sha']
    html = base64.b64decode(api_resp['content']).decode('utf-8')
    
    places, _ = parse_places(html)
    existing_names = [p.get('name','') for p in places]
    print(f'  Existing places: {len(places)}')
    
    prompt = f"""You are a local expert on {name}, {country}. 
Research using {lang}-language sources: local social media (Instagram, TikTok, Facebook groups in {lang}), local travel blogs in {lang}, slow travel blogs, influencer pages from local {lang}-speaking creators.

Find 8-12 NEW places in {name} that are:
- FREE or very cheap to visit
- Known to locals but NOT typical tourist attractions
- Discovered via local {lang} social media, local blogs, slow travel communities
- Include: hidden viewpoints to see the city from above, local neighborhood parks, secret courtyards, local markets, street art spots, community spaces
- Include which local bus number goes there where possible
- The tone is curious, slow, free - like the GoDoStuff app: hidden world, for the curious

DO NOT include: {', '.join(existing_names[:20])}

Return ONLY a JSON array, no markdown, no explanation:
[
  {{
    "name": "Place Name in English",
    "area": "Neighborhood name",
    "desc": "2-3 sentences. Specific local detail. Mention the bus number or tram if known. Why locals love it. Free or cost.",
    "tags": ["viewpoint"|"park"|"market"|"street art"|"local"|"free"|"hidden"],
    "lat": 00.000,
    "lng": 00.000
  }}
]"""
    
    resp = ask_pplx(prompt)
    if not resp:
        print(f'  No response from Perplexity')
        return
    
    new_places = clean_json(resp)
    if not new_places:
        print(f'  Could not parse JSON for {name}')
        print(f'  Raw: {resp[:300]}')
        return
    
    print(f'  Got {len(new_places)} new places')
    
    # Build JS objects for new places
    new_js_items = []
    for p in new_places:
        try:
            pname = str(p.get('name','')).replace("'","\'")
            area = str(p.get('area','')).replace("'","\'")
            desc = str(p.get('desc','')).replace("'","\'")
            tags = p.get('tags',['local','free'])
            if not isinstance(tags, list): tags = ['local','free']
            tags_str = ','.join([f"'{t}'" for t in tags[:4]])
            lat = float(p.get('lat',0))
            lng = float(p.get('lng',0))
            js = f"{{name:'{pname}',area:'{area}',desc:'{desc}',tags:[{tags_str}],lat:{lat},lng:{lng}}}"
            new_js_items.append(js)
        except Exception as e:
            print(f'  Skip place due to: {e}')
    
    if not new_js_items:
        print(f'  No valid places to add')
        return
    
    # Insert into const P = [...]
    insert_str = ',\n  ' + ',\n  '.join(new_js_items)
    new_html = re.sub(r'(const P\s*=\s*\[)', r'\1' + insert_str + ',', html, count=1)
    
    if new_html == html:
        print(f'  Could not inject places')
        return
    
    new_b64 = base64.b64encode(new_html.encode('utf-8')).decode('utf-8')
    status, result = gh_put(
        f'editions/{slug}/index.html',
        new_b64, sha,
        f'enrich {name}: +{len(new_js_items)} places from local {lang} sources'
    )
    if status in (200,201):
        print(f'  Committed {len(new_js_items)} places for {name}')
    else:
        print(f'  Commit failed: {status} - {result.get("message","")}')
    
    time.sleep(5)

if __name__ == '__main__':
    for city in CITIES:
        try:
            enrich_city(city)
        except Exception as e:
            print(f'ERROR on {city["name"]}: {e}')
        time.sleep(3)
    print('\nAll done!')
