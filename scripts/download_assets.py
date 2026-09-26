"""Download the Poly Haven assets listed in asset_plan.json (CC0).
HDRIs: 4k .hdr. Textures and models: 2k .blend with their texture files."""
import json, os, sys, urllib.request, time

ROOT = os.path.join(os.path.dirname(__file__), '..', 'assets')
UA = {'User-Agent': 'property-platform-render/1.0'}

def fetch_json(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA)))

def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + '.part'
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, 'wb') as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
            os.replace(tmp, dest)
            return os.path.getsize(dest)
        except Exception as e:
            print(f'  retry {attempt + 1} {os.path.basename(dest)}: {e}', flush=True)
            time.sleep(3)
    raise RuntimeError(f'failed: {url}')

plan = json.load(open(os.path.join(os.path.dirname(__file__), 'asset_plan.json')))
done = 0
for i, (kind, aid, label, size) in enumerate(plan, 1):
    files = fetch_json(f'https://api.polyhaven.com/files/{aid}')
    if kind == 'HDRI':
        node = files['hdri']['4k']['hdr']
        done += download(node['url'], os.path.join(ROOT, 'hdri', f'{aid}_4k.hdr'))
    else:
        node = files['blend']['2k']['blend']
        base = os.path.join(ROOT, 'textures' if kind == 'Tekstur' else 'models', aid)
        done += download(node['url'], os.path.join(base, os.path.basename(node['url'])))
        for rel, inc in node.get('include', {}).items():
            done += download(inc['url'], os.path.join(base, rel))
    print(f'[{i}/{len(plan)}] {aid} ok  ({done/1e6:.0f} MB so far)', flush=True)
print('ALL DONE', flush=True)
