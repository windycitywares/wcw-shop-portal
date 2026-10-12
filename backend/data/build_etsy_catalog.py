"""How etsy_catalog.json was produced from the scraped Etsy listing data (kept for reference/re-runs).

Input: a JSON list of {id, t(itle), d(escription), p(rice), o(riginal price), q(uantity), sz(sizes), im(ages)}.
"""
import html, json, re, unicodedata, collections
from decimal import Decimal, ROUND_HALF_UP

import sys
raw = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "etsy_raw.json"))
CARD_ORIGINAL = {"4571825072": "180.00", "4571822036": "180.00", "4571136245": "180.00", "4571134015": "180.00", "4571121770": "180.00"}

ROOT = {"slug": "cremation-urns", "name": "Cremation Urns", "parent": None, "sort_order": 0,
        "description": "Memorial urns and matching keepsakes, each featuring artwork chosen to honor a loved one."}
THEMES = [  # (slug, name, description, keyword regexes) — first match wins, in this order
    ("pet-urns", "Pet Urns", "Memorial urns for a beloved companion.", [r"\bpet\b", r"\bdog\b"]),
    ("western-cowboy", "Western & Cowboy", "Cowboy hats, horses and wide-open western skies.", [r"cowboy", r"western"]),
    ("sports-hobbies", "Sports & Hobbies", "For the player, the fan and the lifelong hobbyist.",
     [r"soccer", r"football", r"baseball", r"hockey", r"fishing (at )?sunset", r"sports car", r"steam train", r"seaplane", r"climber", r"firefighter"]),
    ("faith-angels", "Faith & Angels", "Angels, crosses and heavenly scenes of comfort and faith.",
     [r"heaven", r"angel", r"\bcross\b", r"\bmary\b", r"prayer", r"\bdoves?\b"]),
    ("family-love", "Family & Love", "Tributes to mothers, fathers, parents and partners.",
     [r"father", r"\bdad\b", r"mother", r"parents", r"couple", r"romantic", r"\bheart\b"]),
    ("ocean-coastal", "Ocean & Coastal", "Lighthouses, beaches, sea life and rolling waves.",
     [r"sea turtle", r"lighthouse", r"ocean", r"beach", r"starfish", r"mermaid", r"coastal", r"waves"]),
    ("birds-wildlife", "Birds & Wildlife", "Eagles, wolves, lions, songbirds and more.",
     [r"eagle", r"wolf", r"\blion\b", r"tiger", r"alligator", r"ostrich", r"reindeer", r"swan", r"songbird", r"bluebird", r"hummingbird", r"unicorn", r"horse"]),
    ("flowers-butterflies", "Flowers & Butterflies", "Roses, wildflowers, blossoms and butterflies.",
     [r"rose", r"butterfly", r"wildflower", r"blossom", r"dragonfly", r"floral"]),
    ("celestial", "Stars & Cosmos", "Stars, galaxies, nebulae and luminous skies.",
     [r"\bstar\b", r"galaxy", r"nebula", r"geode", r"cosmic", r"saturn"]),
    ("landscapes", "Landscapes & Sunsets", "Mountains, lakes, forests and northern lights.",
     [r"mountain", r"lake", r"forest", r"canyon", r"waterfall", r"northern lights", r"aurora", r"winter", r"cabin", r"bamboo", r"sunset", r"castle"]),
]

def theme_for(title):
    t = title.lower()
    for slug, _, _, pats in THEMES:
        if any(re.search(p, t) for p in pats):
            return slug
    return "landscapes"

def clean_title(t):
    t = re.split(r"\s+[-–]\s+|\s*-\s*Personali[sz]ed\b", t)[0].strip()
    t = re.sub(r"\s+for Human ashes\b", "", t, flags=re.I)
    t = re.sub(r"\bUrns\b", "Urn", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()

def slugify(v):
    v = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")[:80].rstrip("-")

def money(v): return Decimal(v).quantize(Decimal("0.01"), ROUND_HALF_UP)

def key_features(desc):
    out = {}
    for line in desc.splitlines():
        m = re.match(r"^\s*(Material|Finish|Closure|Adult Size|Keepsake Size|Size)\s*:\s*(.+?)\s*$", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out

def norm_material(v):
    v = v.lower()
    for k, name in [("alumin", "Aluminum"), ("brass", "Brass"), ("copper", "Copper"), ("steel", "Steel"), ("wood", "Wood"), ("metal", "Metal")]:
        if k in v: return name
    return None

def norm_finish(v):
    v = v.lower()
    if "gloss" in v: return "High-gloss enamel" if "enamel" in v else "Gloss"
    if "matte" in v: return "Matte"
    return v.strip().capitalize()

slugs = collections.Counter(); products = []
for x in raw:
    title = clean_title(x["t"])
    base = slugify(title); slugs[base] += 1
    slug = base if slugs[base] == 1 else f"{base}-{slugs[base]}"
    price = money(x["p"]); orig = x["o"] or CARD_ORIGINAL.get(x["id"])
    ratio = (price / money(orig)) if orig else None
    feats = key_features(x["d"])
    attrs = {}
    if feats.get("Material") and norm_material(feats["Material"]): attrs["Material"] = norm_material(feats["Material"])
    if feats.get("Finish"): attrs["Finish"] = norm_finish(feats["Finish"])
    short = lambda v: re.split(r"\s+[–-]\s+", v)[0].strip()  # "6 × 10 inches – Suitable for…" → "6 × 10 inches"
    if feats.get("Closure"): attrs["Closure"] = "Threaded screw-top lid" if "screw" in feats["Closure"].lower() else short(feats["Closure"])
    if feats.get("Adult Size"): attrs["Adult urn size"] = short(feats["Adult Size"])
    if feats.get("Keepsake Size"): attrs["Keepsake size"] = short(feats["Keepsake Size"])
    variants = []
    SIZE_NAMES = {"3 inch keepsake": "3 inch Keepsake", "10 inch large": "10 inch Large",
                  "1 large 2 keepsake": "1 Large + 2 Keepsakes", "1 large 4 keepsake": "1 Large + 4 Keepsakes",
                  "3 inch set of 4": "Set of 4 Keepsakes (3 inch)", "3 inch set of 2": "Set of 2 Keepsakes (3 inch)"}
    for name, vp in sorted(x["sz"], key=lambda o: float(o[1] or 0)):
        if not vp: continue
        name = SIZE_NAMES.get(name.lower().strip(), name.strip())
        vp = money(vp)
        variants.append({"name": name, "price": str(vp),
                         "compare_at_price": str((vp / ratio).quantize(Decimal("0.01"), ROUND_HALF_UP)) if ratio else None})
    if variants:
        attrs["Size"] = [v["name"] for v in variants]
    theme = theme_for(x["t"])
    desc = html.unescape(x["d"]).strip()  # Etsy text arrives with &#39; etc.
    first_para = re.split(r"\n\s*\n", desc)[1] if desc.count("\n\n") >= 1 else desc
    products.append({
        "source": "etsy", "source_ref": x["id"], "sku": f"ETSY-{x['id']}", "slug": slug,
        "title": html.unescape(title), "seo_title": html.unescape(x["t"])[:300],
        "seo_description": re.sub(r"\s+", " ", first_para)[:300].rsplit(" ", 1)[0] + "…" if len(first_para) > 300 else re.sub(r"\s+", " ", first_para),
        "description": desc, "category": theme,
        "price": str(min([money(v["price"]) for v in variants] or [price])),
        "compare_at_price": str(money(orig)) if orig else None,
        "quantity": x["q"], "attributes": attrs,
        "tags": ["cremation urn", dict((s, n) for s, n, *_ in THEMES)[theme].lower()],
        "images": [{"url": u, "alt": (a or f"{title} — photo {i+1}")} for i, (u, a) in enumerate(x["im"])],
        "variants": variants,
        "etsy_url": f"https://www.etsy.com/listing/{x['id']}",
    })

cats = [ROOT] + [{"slug": s, "name": n, "description": d, "parent": "cremation-urns", "sort_order": i}
                 for i, (s, n, d, _) in enumerate(THEMES)]
used = collections.Counter(p["category"] for p in products)
cats = [c for c in cats if c["parent"] is None or used[c["slug"]]]
json.dump({"source": "Etsy shop WindyCityWaresUS (https://www.etsy.com/shop/WindyCityWaresUS)", "collected": "2026-10-11",
           "categories": cats, "products": products}, open("backend/data/etsy_catalog.json", "w"), indent=1, ensure_ascii=False)

for c in cats[1:]:
    print(f"\n## {c['name']} ({used[c['slug']]})")
    for p in products:
        if p["category"] == c["slug"]: print("   ", p["title"])
print("\nattributes seen:", collections.Counter(k for p in products for k in p["attributes"]))
print("materials:", collections.Counter(p["attributes"].get("Material") for p in products))
print("finishes:", collections.Counter(p["attributes"].get("Finish") for p in products))
print("variant example:", products[0]["variants"][:3], products[0]["price"], products[0]["compare_at_price"])
print("no-size example:", [(p["title"], p["price"], p["compare_at_price"]) for p in products if not p["variants"]][:2])
