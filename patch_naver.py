import io, sys

def load(p):
    return io.open(p, encoding="utf-8").read()

def save(p, s):
    io.open(p, "w", encoding="utf-8").write(s)

NAVER_FILE = "naver4bb0a34297d9200fa0c6f1417f6d6e3f.html"
NAVER_TAG  = "545a10d00ecef01274542750c9054dc4b9b4f8db"

cb  = load("canibring_v1.py")
ap  = load("app.py")

A1 = ('@cb_bp.route("/googleb66b58b492c65404.html")\n'
      'def cb_google_verify():\n'
      '    return Response("google-site-verification: googleb66b58b492c65404.html",\n'
      '                    mimetype="text/html")\n')

A2 = '\'<meta name="description" content="Whether a medicine is allowed into a country \''

A3 = '_KEEP = ("/%s.txt" % _INKEY,)'

anchors = [("canibring_v1.py A1", cb, A1),
           ("canibring_v1.py A2", cb, A2),
           ("app.py A3",          ap, A3)]
bad = 0
for name, hay, nd in anchors:
    n = hay.count(nd)
    print("%-20s %d" % (name, n))
    if n != 1:
        bad += 1
if bad:
    print("STOP: anchor count != 1, nothing written")
    sys.exit(1)

if NAVER_FILE in cb or NAVER_FILE in ap:
    print("STOP: already applied")
    sys.exit(1)

B1 = A1 + (
 '\n\n'
 '@cb_bp.route("/%s")\n'
 'def cb_naver_verify():\n'
 '    return Response("naver-site-verification: %s",\n'
 '                    mimetype="text/html")\n' % (NAVER_FILE, NAVER_FILE))

B2 = ('\'<meta name="naver-site-verification" content="%s">\'\n'
      '        ' % NAVER_TAG) + A2

B3 = ('_NAVER_HTML = "/%s"\n'
      '_KEEP = ("/%%s.txt" %% _INKEY,\n'
      '         "/googleb66b58b492c65404.html",\n'
      '         _NAVER_HTML)' % NAVER_FILE)

cb = cb.replace(A1, B1, 1).replace(A2, B2, 1)
ap = ap.replace(A3, B3, 1)

for nm, s in (("canibring_v1.py", cb), ("app.py", ap)):
    compile(s, nm, "exec")

save("canibring_v1.py", cb)
save("app.py", ap)
print("WROTE ok")
