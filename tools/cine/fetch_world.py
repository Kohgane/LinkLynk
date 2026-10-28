#!/usr/bin/env python3
"""Open-data world fetch: Copernicus DEM 30m (public, AWS) + Sentinel-2 L2A true color (Copernicus open license, AWS COGs).
Outputs <slug>/dem.npy (float32 meters, north-up rows), <slug>/tex.png, <slug>/meta.json (bbox, size)."""
import sys, os, json, math, urllib.request
import numpy as np
os.environ.setdefault("GDAL_HTTP_PROXY", os.environ.get("HTTPS_PROXY",""))
os.environ.setdefault("CURL_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"; os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif"
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.vrt import WarpedVRT
slug, lon, lat, km = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
N = int(sys.argv[5]) if len(sys.argv) > 5 else 1500   # DEM grid
T = int(sys.argv[6]) if len(sys.argv) > 6 else 4096   # texture size
os.makedirs(slug, exist_ok=True)
dlat = km/111.32/2; dlon = km/(111.32*math.cos(math.radians(lat)))/2
bbox = [lon-dlon, lat-dlat, lon+dlon, lat+dlat]
dst_crs = "EPSG:4326"
def grid_transform(n): return rasterio.transform.from_bounds(*bbox, n, n)

# P23-1028: inside the contiguous US we take USGS 3DEP (10 m DEM) + The National Map orthoimagery (~1 m) — public domain, no key
US = (-125.0 <= bbox[0]) and (bbox[2] <= -66.5) and (24.0 <= bbox[1]) and (bbox[3] <= 49.5)
def arcgis_image(base, extra, w, h, fmt):
    u = f"{base}?bbox={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}&bboxSR=4326&imageSR=4326&size={w},{h}&format={fmt}&f=image{extra}"
    return urllib.request.urlopen(u, timeout=180).read()

# --- DEM: Copernicus GLO-30 tiles are 1x1 degree COGs ---
dem = np.zeros((N, N), np.float32); dem_hit = np.zeros((N, N), bool)
if US:
    try:
        import io as _io
        raw = arcgis_image("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage", "&pixelType=F32&noDataInterpretation=esriNoDataMatchAny&interpolation=RSP_BilinearInterpolation", min(N, 4096), min(N, 4096), "tiff")
        with rasterio.open(_io.BytesIO(raw)) as src:
            a = src.read(1).astype(np.float32)
        if a.shape != (N, N):
            from PIL import Image as _I; a = np.asarray(_I.fromarray(a).resize((N, N), _I.BILINEAR), np.float32)
        ok = np.isfinite(a) & (a > -1000); dem[ok] = a[ok]; dem_hit |= ok
        print("dem usgs-3dep", int(ok.sum()))
    except Exception as e: print("3dep miss", str(e)[:80])
for la in (range(math.floor(bbox[1]), math.floor(bbox[3])+1) if dem_hit.mean() < 0.999 else []):
    for lo in range(math.floor(bbox[0]), math.floor(bbox[2])+1):
        ns = ("N%02d" % la) if la >= 0 else ("S%02d" % -la); ew = ("E%03d" % lo) if lo >= 0 else ("W%03d" % -lo)
        name = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
        url = f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
        try:
            with rasterio.open(url) as src:
                out = np.full((N, N), np.nan, np.float32)
                reproject(rasterio.band(src, 1), out, dst_transform=grid_transform(N), dst_crs=dst_crs, resampling=Resampling.bilinear, dst_nodata=np.nan)
                m = ~np.isnan(out) & ~dem_hit; dem[m] = out[m]; dem_hit |= m
                print("dem", name, int(m.sum()))
        except Exception as e: print("dem miss", name, str(e)[:80])
dem[~dem_hit] = 0.0
np.save(f"{slug}/dem.npy", dem)

# --- Sentinel-2 true color via earth-search STAC ---
q = {"collections":["sentinel-2-l2a"], "bbox":bbox, "datetime":"2023-01-01T00:00:00Z/2026-12-31T00:00:00Z",
     "query":{"eo:cloud_cover":{"lt":12}}, "limit":100, "sortby":[{"field":"properties.eo:cloud_cover","direction":"asc"}]}
req = urllib.request.Request("https://earth-search.aws.element84.com/v1/search", data=json.dumps(q).encode(), headers={"content-type":"application/json"})
feats = [] if (T/km) < 12 or US else json.load(urllib.request.urlopen(req, timeout=60))["features"]  # coarse rings: Blue Marble only
tex = np.zeros((3, T, T), np.uint8); hit = np.zeros((T, T), bool)
if US and (T/km) >= 12:
    # The National Map orthoimagery export caps at 4096 px per request -> fetch a grid of sub-boxes and stitch
    from PIL import Image as _I; import io as _io
    n = max(1, math.ceil(T / 4096)); step = T // n
    for gy in range(n):
        for gx in range(n):
            x0, x1 = gx*step, (T if gx == n-1 else (gx+1)*step); y0, y1 = gy*step, (T if gy == n-1 else (gy+1)*step)
            sb = [bbox[0] + (bbox[2]-bbox[0])*x0/T, bbox[3] - (bbox[3]-bbox[1])*y1/T, bbox[0] + (bbox[2]-bbox[0])*x1/T, bbox[3] - (bbox[3]-bbox[1])*y0/T]
            u = f"https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export?bbox={sb[0]},{sb[1]},{sb[2]},{sb[3]}&bboxSR=4326&imageSR=4326&size={x1-x0},{y1-y0}&format=jpg&f=image"
            try:
                im = np.asarray(_I.open(_io.BytesIO(urllib.request.urlopen(u, timeout=180).read())).convert("RGB"))
                tex[:, y0:y1, x0:x1] = np.moveaxis(im, -1, 0); hit[y0:y1, x0:x1] = True
                print("usgs ortho", gx, gy, im.shape)
            except Exception as e: print("usgs miss", gx, gy, str(e)[:80])
# prefer months close to each other (same season) by taking the best scene per MGRS tile
# prefer the leafy months (May-Oct north / Nov-Apr south of the equator), then lowest cloud; any scene that adds pixels is used
def season_key(f):
    m = int(f["properties"]["datetime"][5:7]); summer = (5 <= m <= 10) if lat >= 0 else (m >= 11 or m <= 4)
    return (0 if summer else 1, f["properties"]["eo:cloud_cover"])
feats.sort(key=season_key)
for f in feats:
    if hit.mean() > 0.995: break
    href = f["assets"]["visual"]["href"]
    try:
        with rasterio.open(href) as src:
            with WarpedVRT(src, crs=dst_crs, resampling=Resampling.bilinear) as vrt:
                out = np.zeros((3, T, T), np.uint8)
                reproject(rasterio.band(vrt, [1,2,3]), out, dst_transform=grid_transform(T), dst_crs=dst_crs, resampling=Resampling.bilinear, dst_nodata=0)
                m = (out.max(axis=0) > 0) & ~hit
                if m.sum() < T*T*0.005: continue
                for b in range(3): tex[b][m] = out[b][m]
                hit |= m
                print("s2", f["id"], f["properties"]["datetime"][:10], f["properties"]["eo:cloud_cover"], int(m.sum()))
    except Exception as e: print("s2 miss", f["id"], str(e)[:80])
from PIL import Image
# --- fill whatever Sentinel left (clouds / scene limits) with NASA Blue Marble NG (public domain, ~300 m) ---
if hit.mean() < 0.999:
    z = 7; tsz = 360.0/[2,3,5,10,20,40,80,160][z]; dpp = tsz/512   # GIBS EPSG:4326 "500m" matrix widths
    c0, c1 = int((bbox[0]+180)//tsz), int((bbox[2]+180)//tsz); r0, r1 = int((90-bbox[3])//tsz), int((90-bbox[1])//tsz)
    W = (c1-c0+1)*512; Hh = (r1-r0+1)*512
    mosaic = Image.new("RGB", (W, Hh))
    for r in range(r0, r1+1):
        for c in range(c0, c1+1):
            u = f"https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/BlueMarble_NextGeneration/default/500m/{z}/{r}/{c}.jpeg"
            try:
                import io as _io; mosaic.paste(Image.open(_io.BytesIO(urllib.request.urlopen(u, timeout=60).read())).convert("RGB"), ((c-c0)*512, (r-r0)*512))
            except Exception as e: print("bm miss", r, c, str(e)[:60])
    # crop the bbox out of the mosaic (lon/lat -> mosaic px) and resample to T
    px0 = (bbox[0] - (c0*tsz-180))/dpp; px1 = (bbox[2] - (c0*tsz-180))/dpp
    py0 = ((90 - r0*tsz) - bbox[3])/dpp; py1 = ((90 - r0*tsz) - bbox[1])/dpp
    fill = np.asarray(mosaic.crop((int(px0), int(py0), int(px1)+1, int(py1)+1)).resize((T, T), Image.BILINEAR))
    # match Blue Marble brightness to the Sentinel pixels we do have, then blend in with a soft edge
    if hit.mean() > 0.05:
        g = tex[:, hit].astype(np.float32).mean(); gb = np.moveaxis(fill, -1, 0)[:, hit].astype(np.float32).mean()
        fill = np.clip(fill.astype(np.float32) * (g/max(gb, 1.0)), 0, 255)
    from scipy.ndimage import uniform_filter
    soft = np.clip(uniform_filter(hit.astype(np.float32), 25), 0, 1)
    tex = (tex.astype(np.float32) * soft + np.moveaxis(fill, -1, 0).astype(np.float32) * (1-soft)).astype(np.uint8)
    print("bluemarble fill", float(1-hit.mean()))
Image.fromarray(np.moveaxis(tex, 0, -1)).save(f"{slug}/tex.png")
json.dump({"slug":slug, "lon":lon, "lat":lat, "km":km, "bbox":bbox, "N":N, "T":T, "cover":float(hit.mean()), "dem_min":float(dem.min()), "dem_max":float(dem.max())}, open(f"{slug}/meta.json","w"))
print("done cover=%.3f dem %.0f..%.0f" % (hit.mean(), dem.min(), dem.max()))
