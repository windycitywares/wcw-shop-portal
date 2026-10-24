import { isLocale, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { getShopConfig } from "@/lib/api";
import { SHOP_PLATFORMS } from "@/lib/shopPlatforms";

export const revalidate = 300;

/**
 * A one-line embed for other sites (windycitywares.com): <script src="https://shop.windycitywares.com/embed/marketplaces.js" defer>.
 * It draws the same marketplace tiles as the shop's own pages from the list in Admin → Settings → Marketplaces,
 * so the main site never needs editing when a shop is added. Add ?lang=es or ?lang=nl for another language.
 */
export async function GET(request: Request) {
  const asked = new URL(request.url).searchParams.get("lang");
  const lang: Locale = isLocale(asked) ? asked : "en";
  const t = getDictionary(lang).home;
  const config = await getShopConfig(lang);
  const data = {
    links: config?.shop_links ?? [],
    platforms: Object.fromEntries(SHOP_PLATFORMS.map((p) => [p.id, { label: p.label, bg: p.bg, fg: p.fg }])),
    text: { title: t.shopsTitle, intro: t.shopsText, on: t.shopOn, opens: t.shopOpens, soon: t.shopSoon, notice: t.shopsNotice },
  };
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  const js = `(function(){
var D=${json};
if(!D.links.length)return;
var host=document.getElementById("wcw-marketplaces");
if(!host){host=document.createElement("section");var f=document.querySelector("footer");(f&&f.parentNode)?f.parentNode.insertBefore(host,f):document.body.appendChild(host);}
host.setAttribute("aria-labelledby","wcw-mk-h");
var css=document.createElement("style");
css.textContent=".wcw-mk{max-width:80rem;margin:0 auto;padding:3rem 1rem;font-family:inherit}.wcw-mk h2{margin:0;font-size:1.9rem;font-weight:400}.wcw-mk p{margin:.5rem 0 0;color:#5b6770}.wcw-mk ul{list-style:none;margin:2rem 0 0;padding:0;display:grid;gap:1rem;grid-template-columns:repeat(auto-fill,minmax(13.5rem,1fr))}.wcw-mk li{position:relative}.wcw-mk a,.wcw-mk .soon{display:flex;align-items:center;gap:.75rem;height:100%;box-sizing:border-box;padding:.75rem;background:#fff;border:1px solid #e2e5e7;border-radius:12px;text-decoration:none;color:#17232b;box-shadow:0 1px 2px rgba(0,0,0,.06);transition:transform .2s,box-shadow .2s}.wcw-mk a:hover,.wcw-mk a:focus-visible{transform:translateY(-2px);box-shadow:0 10px 24px -12px rgba(0,0,0,.35)}.wcw-mk .b{flex:none;width:2.75rem;height:2.75rem;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:1.1rem}.wcw-mk .l{flex:none;width:3.5rem;height:2.75rem;background:#fff;border-radius:8px;box-shadow:inset 0 0 0 1px #e2e5e7;display:grid;place-items:center;padding:6px;box-sizing:border-box}.wcw-mk .l img{max-width:100%;max-height:100%;object-fit:contain}.wcw-mk .n{display:block;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.wcw-mk .s{display:block;font-size:.85rem;color:#5b6770}.wcw-mk .tip{display:none;position:absolute;bottom:100%;left:50%;transform:translateX(-50%);margin-bottom:.5rem;width:16rem;padding:.75rem;background:#17232b;color:#fff;border-radius:12px;font-size:.85rem;z-index:30;pointer-events:none;box-shadow:0 12px 30px rgba(0,0,0,.35)}.wcw-mk li:hover .tip,.wcw-mk li:focus-within .tip{display:block}.wcw-mk .fine{font-size:.75rem;margin-top:1.5rem;max-width:42rem}@media(max-width:768px){.wcw-mk .tip{display:none!important}}.wcw-mk .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}";
document.head.appendChild(css);
function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e;}
var wrap=el("div","wcw-mk");
var h=el("h2",null,D.text.title);h.id="wcw-mk-h";wrap.appendChild(h);
wrap.appendChild(el("p",null,D.text.intro));
var ul=el("ul");
D.links.forEach(function(l){
 var p=D.platforms[l.platform]||D.platforms.other;
 var li=el("li");
 var soon=l.url==="#";
 var card=soon?el("div","soon"):el("a");
 if(!soon){card.href=l.url;card.target="_blank";card.rel="noopener noreferrer";}
 var badge;
 if(l.image_url&&!soon){badge=el("span","l");var im=el("img");im.src=l.image_url;im.alt="";im.loading="lazy";im.referrerPolicy="no-referrer";badge.appendChild(im);}
 else{badge=el("span","b",(l.platform==="other"?l.name:p.label).charAt(0).toUpperCase());badge.style.background=p.bg;badge.style.color=p.fg;}
 badge.setAttribute("aria-hidden","true");
 card.style.borderLeft="6px solid "+p.bg;
 var txt=el("span");
 txt.appendChild(el("span","n",l.name));
 txt.appendChild(el("span","s",soon?D.text.soon:(l.platform==="other"?D.text.opens:D.text.on.replace("{platform}",p.label))));
 card.appendChild(badge);card.appendChild(txt);
 if(!soon){var sr=el("span","sr"," ("+D.text.opens+")");card.appendChild(sr);}
 li.appendChild(card);
 if(l.blurb&&!soon){var tip=el("span","tip");tip.setAttribute("role","tooltip");tip.appendChild(el("strong",null,l.name));tip.appendChild(el("span",null,l.blurb));tip.firstChild.style.display="block";tip.lastChild.style.display="block";tip.lastChild.style.marginTop=".25rem";li.appendChild(tip);}
 ul.appendChild(li);
});
wrap.appendChild(ul);
wrap.appendChild(el("p","fine",D.text.notice));
host.appendChild(wrap);
})();
`;
  return new Response(js, {
    headers: {
      "Content-Type": "text/javascript; charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=300",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
