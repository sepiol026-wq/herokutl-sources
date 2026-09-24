import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from packaging.version import parse

def get_latest_version():
    req = urllib.request.Request(
        'https://pypi.org/pypi/herokutl/json',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    releases = data['releases']
    valid_versions = [v for v, files in releases.items() if files]
    def sort_key(v):
        try:
            return (1, parse(v))
        except Exception:
            return (0, v)
    valid_versions.sort(key=sort_key)
    latest_v = valid_versions[-1]
    files = releases[latest_v]
    sdist = next((f for f in files if f.get('packagetype') == 'sdist'), None)
    target = sdist or next((f for f in files if f.get('packagetype') == 'bdist_wheel'), None) or files[0]
    return latest_v, target

def sync(repo_root):
    latest_v, target = get_latest_version()
    with tempfile.TemporaryDirectory() as td:
        archive_path = os.path.join(td, target['filename'])
        urllib.request.urlretrieve(target['url'], archive_path)
        extracted = os.path.join(td, 'extracted')
        os.makedirs(extracted, exist_ok=True)
        if target['filename'].endswith(('.tar.gz', '.tgz', '.tar.bz2', '.tar')):
            with tarfile.open(archive_path) as t:
                members = t.getmembers()
                names = [m.name for m in members if m.name]
                prefix = os.path.commonpath(names) if names else ''
                for m in members:
                    rel = os.path.relpath(m.name, prefix) if prefix else m.name
                    if rel == '.':
                        continue
                    dest = os.path.join(extracted, rel)
                    if m.isdir():
                        os.makedirs(dest, exist_ok=True)
                    elif m.isfile():
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with t.extractfile(m) as src, open(dest, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
        elif target['filename'].endswith(('.zip', '.whl')):
            with zipfile.ZipFile(archive_path) as z:
                names = [n for n in z.namelist() if n]
                prefix = os.path.commonpath(names) if names else ''
                has_single_root = bool(prefix and all(n.startswith(prefix + '/') or n == prefix for n in names))
                for n in names:
                    rel = os.path.relpath(n, prefix) if has_single_root else n
                    if rel == '.':
                        continue
                    dest = os.path.join(extracted, rel)
                    if n.endswith('/'):
                        os.makedirs(dest, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with z.open(n) as src, open(dest, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
        for item in os.listdir(repo_root):
            if item in ('.git', '.github'):
                continue
            item_path = os.path.join(repo_root, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
        for item in os.listdir(extracted):
            src_item = os.path.join(extracted, item)
            dst_item = os.path.join(repo_root, item)
            if item == '.github':
                continue
            if os.path.isdir(src_item):
                shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
            else:
                shutil.copy2(src_item, dst_item)
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a', encoding='utf-8') as f:
            f.write(f'version={latest_v}\n')
    print(latest_v)

if __name__ == '__main__':
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sync(root_dir)
