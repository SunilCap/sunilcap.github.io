#!/usr/bin/env python3
"""Scotcha site builder.

Add or edit a game = put games/<slug>/index.html and games/<slug>/game.json in the repo.
This script then regenerates every place that lists games:
  home page tiles, games list, about page, privacy "saved data" list, terms (stars),
  sitemap.xml, the offline cache list in sw.js, and (if missing) the game's guide + manifest.
Only the parts between <!-- AUTO:name --> ... <!-- /AUTO:name --> markers are rewritten.
Everything else in the pages is yours to edit by hand.   Run locally:  python3 scripts/build.py
"""
import glob, hashlib, html, json, os, re, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
TODAY = datetime.date.today().isoformat()
WARN = []

def esc(t): return html.escape(str(t), quote=False)
def read(p): return open(p, encoding='utf-8').read()
def write(p, t):
    if os.path.exists(p) and read(p) == t: return False
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    open(p, 'w', encoding='utf-8').write(t); print('  updated', p); return True
def join(names, oxford=True):
    n = len(names)
    if n == 0: return ''
    if n == 1: return names[0]
    if n == 2: return f'{names[0]} and {names[1]}'
    return ', '.join(names[:-1]) + (', and ' if oxford else ' and ') + names[-1]

# ---------- load games ----------
games = []
for f in glob.glob('games/*/game.json'):
    slug = os.path.basename(os.path.dirname(f))
    try: g = json.loads(read(f))
    except Exception as e: WARN.append(f'{f}: invalid JSON ({e})'); continue
    for k in ('title', 'description'):
        if not g.get(k): WARN.append(f'{f}: missing "{k}"')
    if not os.path.exists(f'games/{slug}/index.html'): WARN.append(f'games/{slug}/: no index.html yet')
    g['slug'] = slug
    g.setdefault('title', slug.replace('-', ' ').title()); g.setdefault('emoji', '🎮'); g.setdefault('description', '')
    g.setdefault('tagline', g['title']); g.setdefault('bestFor', 'quick sessions.'); g.setdefault('controlsLabel', 'Controls')
    g.setdefault('guideLabel', 'How to play'); g.setdefault('order', 100)
    g['tileHead'] = g.get('tileHead', g['tagline']); g['tileBody'] = g.get('tileBody', g['description'])
    g['short'] = g.get('short', g['description']); g['about'] = g.get('about', g['description'])
    g['guideHome'] = g.get('guideHome', g['guideLabel']); g['guideList'] = g.get('guideList', g['guideLabel'])
    g['extraLabel'] = g.get('extraLabel', g['controlsLabel']); g['extraText'] = g.get('extraText', g.get('controls', ''))
    g['glance'] = g.get('glance', g.get('controls', ''))
    games.append(g)
games.sort(key=lambda g: (g['order'], g['title']))
names = [g['title'] for g in games]
print(f'{len(games)} games:', ', '.join(names))

# ---------- marker helpers ----------
def block(text, name, content, path):
    pat = re.compile(r'(<!-- AUTO:%s -->)(.*?)(<!-- /AUTO:%s -->)' % (name, name), re.S)
    if not pat.search(text): WARN.append(f'{path}: marker AUTO:{name} not found'); return text
    return pat.sub(lambda m: m.group(1) + ('\n' + content + '\n' if content else '') + m.group(3), text, count=1)
def desc(text):
    pat = re.compile(r'<!--AUTO-DESC:(.*?)-->\s*<meta name="description" content="[^"]*">', re.S)
    def f(m):
        d = m.group(1).replace('{names}', join(names)).replace('{names_plain}', join(names, False))
        return f'<!--AUTO-DESC:{m.group(1)}-->\n<meta name="description" content="{html.escape(d)}">'
    return pat.sub(f, text)
def edit(path, fn):
    if not os.path.exists(path): WARN.append(f'{path}: missing'); return
    write(path, fn(read(path)))

# ---------- page sections ----------
def tile(g):
    s, t = g['slug'], esc(g['title'])
    extra = f'<p><strong>{esc(g["extraLabel"])}:</strong> {esc(g["extraText"])}</p>' if g['extraText'] else ''
    return (f'<article class="game"><button class="game-tile" type="button" aria-expanded="false" aria-controls="{s}-details" data-game-toggle="{s}-details">'
            f'<span class="game-icon" aria-hidden="true">{g["emoji"]}</span><h3>{t}</h3><span class="tap-hint">Tap to explore ↓</span></button>'
            f'<div class="game-details" id="{s}-details" hidden><p><strong>{esc(g["tileHead"])}</strong> {esc(g["tileBody"])}</p>'
            f'<p><strong>Best for:</strong> {esc(g["bestFor"])}</p>{extra}'
            f'<a class="button" href="/games/{s}/">Play {t}</a><a class="button secondary" href="/games/{s}/guide.html">{esc(g["guideHome"])}</a></div></article>')
def listing(g):
    s, t = g['slug'], esc(g['title'])
    return f'<h3>{g["emoji"]} {t}</h3><p>{esc(g["short"])}</p><p><a href="/games/{s}/">Play {t}</a> · <a href="/games/{s}/guide.html">{esc(g["guideList"])}</a></p>'
def about(g):
    s, t = g['slug'], esc(g['title'])
    return f'<h3>{t}</h3><p>{esc(g["about"])}</p><p><a href="/games/{s}/">Play {t}</a> · <a href="/games/{s}/guide.html">Read the {t} guide</a></p>'

savers = [g for g in games if g.get('saves')]
nosave = [g for g in games if not g.get('saves')]
star_games = [g['title'] for g in games if g.get('stars')]
share_games = [g['title'] for g in games if g.get('share')]
sound_games = [g['title'] for g in games if g.get('sound')]

def home(t):
    t = desc(block(t, 'home-tiles', '\n'.join(tile(g) for g in games), 'index.html'))
    n = [g['title'] for g in savers]
    s = ''
    if n:
        s = f'{join(n)} {"stores" if len(n) == 1 else "store"} your personal best'
        if star_games: s += f' (and, in {join(star_games)}, your banked stars)'
        s += " in your browser's local storage when that feature is available; clearing browser data may reset it."
    t = block(t, 'home-saves', s, 'index.html')
    li = [f'<li><strong>{esc(g["title"])}:</strong> {esc(g["glance"])}</li>' for g in games if g['glance']]
    if sound_games: li.append(f'<li>{join(sound_games)} {"has" if len(sound_games) == 1 else "have"} a sound control to mute or enable synthesized sound.</li>')
    return block(t, 'home-controls', ''.join(li), 'index.html')
def gamelist(t): return desc(block(t, 'list-games', ''.join(listing(g) for g in games), 'games/index.html'))
def aboutpage(t): return desc(block(t, 'about-games', ''.join(about(g) for g in games), 'about.html'))
def privacy(t):
    li = [f'<li><strong>{esc(g["title"])}</strong> saves {esc(g["saves"])}.</li>' for g in savers]
    li += [f'<li><strong>{esc(g["title"])}</strong> does not save scores.</li>' for g in nosave]
    t = block(t, 'privacy-saves', ''.join(li), 'privacy.html')
    if share_games:
        p = (f'<p>The Share {"button" if len(share_games) == 1 else "buttons"} in {join(share_games)} {"opens" if len(share_games) == 1 else "open"} your device\'s own share menu or copy a link to your clipboard. '
             'We do not receive what you share or who you share it with.</p>')
    else: p = '<p>The games do not currently include a share feature.</p>'
    return block(t, 'privacy-share', p, 'privacy.html')
def terms(t):
    p = (f'<p>Stars in {join(star_games)} are virtual in-game items. They have no cash value, cannot be bought, sold, transferred or exchanged for money or prizes, and may be changed or reset when the game is updated.</p>') if star_games else ''
    return block(t, 'terms-stars', p, 'terms.html')

# ---------- per-game helpers: guide + manifest (only if missing) ----------
GUIDE_CSS = ':root{color-scheme:light;--ink:#2b1b0e;--line:#ead9bd}*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--ink);background:linear-gradient(180deg,#fff3cc,#fffaf0 340px);line-height:1.65}header{padding:24px 20px;border-bottom:1px solid var(--line);background:#fff8e8}nav,main,footer{max-width:980px;margin:auto;padding-left:20px;padding-right:20px}nav{display:flex;gap:16px;flex-wrap:wrap;align-items:center}nav a,.footerlinks a,.panel a{color:#74400e;font-weight:650}nav .brand{margin-right:auto;font-weight:850;text-decoration:none;color:var(--ink)}main{padding-top:28px;padding-bottom:48px}.hero,.panel{background:rgba(255,255,255,.85);border:1px solid var(--line);border-radius:18px;padding:clamp(20px,4vw,34px);margin:18px 0;box-shadow:0 6px 24px #6b45100c}h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.1;margin:.25em 0 .5em}h2{margin-top:1.1em;line-height:1.25}h2:first-child{margin-top:0}.eyebrow{font-size:.78rem;letter-spacing:.13em;text-transform:uppercase;font-weight:800;color:#a45b0b;margin:0}.button{display:inline-flex;align-items:center;justify-content:center;background:#ffdb59;color:#2b1b0e!important;padding:10px 18px;border-radius:10px;border:2px solid #2b1b0e;text-decoration:none;font-weight:800;margin:8px 8px 0 0}.button.secondary{background:#fff}ul,ol{padding-left:1.4em}li{margin:.35em 0}table{border-collapse:collapse;width:100%;margin:.5em 0}th,td{border:1px solid var(--line);padding:8px 10px;text-align:left}th{background:#fff3d5}footer{padding-top:20px;padding-bottom:30px;border-top:1px solid var(--line);font-size:.9rem;color:#665747}.footerlinks{display:flex;gap:14px;flex-wrap:wrap}a:focus-visible{outline:3px solid #1769aa;outline-offset:3px}@media(max-width:560px){header{padding:18px 0}nav{gap:10px}.hero,.panel{padding:20px}}'
GUIDE_TPL = lambda h: h.replace('@@CSS@@', GUIDE_CSS)
def make_guide(g):
    s, t = g['slug'], esc(g['title']); gd = g.get('guide', {})
    goal = esc(gd.get('goal', g['description']))
    ctl = gd.get('controls')
    ctable = ''
    if ctl: ctable = '<h2>Controls</h2><table><thead><tr><th>Action</th><th>Touch or mouse</th><th>Keyboard</th></tr></thead><tbody>' + ''.join(f'<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>' for a, b, c in ctl) + '</tbody></table>'
    elif g['extraText']: ctable = f'<h2>{esc(g["extraLabel"])}</h2><p>{esc(g["extraText"][0].upper() + g["extraText"][1:])}</p>'
    tips = '<h2>Tips</h2><ul>' + ''.join(f'<li>{esc(x)}</li>' for x in gd['tips']) + '</ul>' if gd.get('tips') else ''
    faq = ''.join(f'<p><strong>{esc(q)}</strong> {esc(a)}</p>' for q, a in gd.get('faq', []))
    faq += '<p><strong>Can I play offline?</strong> Yes. Once you have opened the game, you can add it to your home screen and play it like an app, including offline.</p>'
    faq += '<p><strong>Why do ads appear?</strong> Scotcha is free to play and supported by Google ads, which may appear between rounds. If ads are blocked or unavailable, the game continues normally.</p>'
    if g.get('saves'): faq = f'<p><strong>Is my progress saved?</strong> The game saves {esc(g["saves"])} in your browser on your device. Clearing your browser data removes it. See the <a href="/privacy.html">Privacy Policy</a>.</p>' + faq
    return GUIDE_TPL(f'''<!-- generated by build: delete this line and edit freely to take over this page -->
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="How to play {html.escape(g["title"])}: {html.escape(g["tagline"])} Controls, tips and FAQ."><link rel="canonical" href="https://scotcha.in/games/{s}/guide.html"><meta name="theme-color" content="#fff3cc"><link rel="manifest" href="/manifest.webmanifest"><link rel="icon" type="image/png" sizes="64x64" href="/icons/favicon-64.png"><link rel="apple-touch-icon" href="/icons/apple-touch-icon.png"><title>How to Play {t} | Scotcha</title><style>@@CSS@@</style></head><body><header><nav><a class="brand" href="/">Scotcha</a><a href="/games/">Games</a><a href="/about.html">About</a><a href="/contact.html">Contact</a></nav></header><main><section class="hero"><p class="eyebrow">Game guide</p><h1>How to play {t}</h1><p>{esc(g["description"])}</p><p><a class="button" href="/games/{s}/">Play {t}</a><a class="button secondary" href="/games/">All games</a></p></section>
<section class="panel"><h2>The goal</h2><p>{goal}</p>{ctable}{tips}<h2>Questions</h2>{faq}</section></main><footer><div class="footerlinks"><a href="/games/">Games</a><a href="/about.html">About</a><a href="/contact.html">Contact</a><a href="/privacy.html">Privacy Policy</a><a href="/terms.html">Terms of Use</a></div><p>Independent browser-game projects. Game availability and features may change as projects are updated.</p></footer><script>if('serviceWorker' in navigator)addEventListener('load',function(){{navigator.serviceWorker.register('/sw.js').catch(function(){{}})}});</script></body></html>
''')
def make_manifest(g):
    s = g['slug']; ic = f'/icons/{s}-192.png' if os.path.exists(f'icons/{s}-192.png') else None
    icons = ([{'src': f'/icons/{s}-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'}, {'src': f'/icons/{s}-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}]
             if ic else [{'src': '/icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'}, {'src': '/icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'}])
    return json.dumps({'name': f'{g["title"]} – Scotcha', 'short_name': g['title'][:12], 'description': g['description'], 'id': f'/games/{s}/', 'start_url': f'/games/{s}/', 'scope': f'/games/{s}/',
                       'display': 'standalone', 'orientation': 'portrait', 'background_color': g.get('themeColor', '#fff3cc'), 'theme_color': g.get('themeColor', '#fff3cc'), 'icons': icons}, indent=2, ensure_ascii=False) + '\n'

def validate(g):
    p = f'games/{g["slug"]}/index.html'
    if not os.path.exists(p): return
    t = read(p)
    for needle, msg in [('adsbygoogle', 'no Google ads script'), ('adBreak', 'no adBreak() interstitial hook'), ('scotcha.in', 'no Scotcha badge'),
                        ('name="viewport"', 'no viewport meta tag'), ('rel="manifest"', 'no manifest link'), ("serviceWorker", 'no service-worker registration')]:
        if needle not in t: WARN.append(f'{p}: {msg}')

for g in games:
    validate(g)
    gp = f'games/{g["slug"]}/guide.html'
    if not os.path.exists(gp) or read(gp).startswith('<!-- generated by build'): write(gp, make_guide(g))
    mp = f'games/{g["slug"]}/manifest.webmanifest'
    if not os.path.exists(mp): write(mp, make_manifest(g))

for path, fn in [('index.html', home), ('games/index.html', gamelist), ('about.html', aboutpage), ('privacy.html', privacy), ('terms.html', terms)]: edit(path, fn)

# ---------- sitemap ----------
def mtime(path, url, old):
    try:
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', path], capture_output=True, text=True).stdout.strip()
        if dirty: return TODAY
        d = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', path], capture_output=True, text=True).stdout.strip()
        if d: return d
    except Exception: pass
    return old.get(url, TODAY)
old = dict(re.findall(r'<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>', read('sitemap.xml'))) if os.path.exists('sitemap.xml') else {}
urls = [('/', 'index.html'), ('/games/', 'games/index.html'), ('/about.html', 'about.html'), ('/contact.html', 'contact.html'), ('/privacy.html', 'privacy.html'), ('/terms.html', 'terms.html')]
for g in games:
    s = g['slug']; urls += [(f'/games/{s}/', f'games/{s}/index.html'), (f'/games/{s}/guide.html', f'games/{s}/guide.html')]
sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(
    f'<url><loc>https://scotcha.in{u}</loc><lastmod>{mtime(f, "https://scotcha.in" + u, old)}</lastmod></url>\n' for u, f in urls) + '</urlset>\n'
write('sitemap.xml', sm)

# ---------- service worker: precache list + auto version ----------
static = ['/', '/games/', '/404.html', '/about.html', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/icon-maskable-512.png', '/icons/apple-touch-icon.png', '/icons/favicon-64.png']
pre = list(static); h = hashlib.sha1()
for g in games:
    d = f'games/{g["slug"]}'
    for f in sorted(glob.glob(d + '/*')):
        b = os.path.basename(f)
        if b in ('game.json',) or b.endswith('.md') or not os.path.isfile(f): continue
        pre.append(f'/{d}/' if b == 'index.html' else f'/{f}'); h.update(open(f, 'rb').read())
    for sz in (192, 512):
        if os.path.exists(f'icons/{g["slug"]}-{sz}.png'): pre.append(f'/icons/{g["slug"]}-{sz}.png')
for f in ['index.html', 'about.html', 'privacy.html', 'terms.html', 'games/index.html']:
    if os.path.exists(f): h.update(open(f, 'rb').read())
if os.path.exists('sw.js'):
    t = read('sw.js')
    ver = 'scotcha-' + h.hexdigest()[:8]
    t = re.sub(r"const VERSION = '[^']*';", f"const VERSION = '{ver}';", t, count=1)
    arr = ',\n'.join(f"  '{p}'" for p in dict.fromkeys(pre))
    pat = re.compile(r'(// AUTO:precache\n)(.*?)(// /AUTO:precache)', re.S)
    if pat.search(t): t = pat.sub(lambda m: m.group(1) + 'const PRECACHE = [\n' + arr + '\n];\n' + m.group(3), t, count=1)
    else: WARN.append('sw.js: marker AUTO:precache not found')
    write('sw.js', t)

print('\nDone.' + (' Warnings:' if WARN else ' No warnings.'))
for w in WARN: print('  WARNING', w)
