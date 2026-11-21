"""The page's HTML: the frame the script fills in. The top bar, the five views (the map, an account, its score, the list
and How it works), the phone's tab bar, the tour's card and the footer. The map, the account and the score sit in one
strip, so a phone swipes between them as three screens while a wider window shows one at a time.

Every visible word comes from WORDS.md. No inline style or script, so the site's security policy can stay strict.
"""
from html import escape as esc

SCRIPTS = ("data.js", "scoring.js", "route.js", "claims.js", "app.js")
HOME = "https://www.ryansansbury.com/"
LIVE = HOME + "account-signals/"
# The link preview's image is the top 838 rows of the homepage card, which is 1.91 to 1 and needs no crop on LinkedIn.
SHARE = HOME + "images/share/account-signals.png?v=1"
MARK = ('<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true"><rect width="28" height="28" rx="8" '
        'fill="#ea580c"/><circle cx="14" cy="14" r="3" fill="#fff"/><circle cx="14" cy="14" r="7" fill="none" '
        'stroke="#fff" stroke-width="1.8" opacity=".8"/><circle cx="14" cy="14" r="11" fill="none" stroke="#fff" '
        'stroke-width="1.5" opacity=".45"/></svg>')
THEME = ("<svg class='moon' viewBox='0 0 24 24' aria-hidden='true' focusable='false'><path d='M20 14.5A8.5 8.5 0 0 1 9.5 4a"
         "8.5 8.5 0 1 0 10.5 10.5z'/></svg><svg class='sun' viewBox='0 0 24 24' aria-hidden='true' focusable='false'>"
         "<circle cx='12' cy='12' r='4'/><path d='M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 "
         "19.1l1.4-1.4M17.7 6.3l1.4-1.4'/></svg>")


def long_date(iso, w):
    """2026-11-09 as November 9, in WORDS.md's month names."""
    if not iso:
        return ""
    months = w["ui.months"].split()
    return f"{months[int(iso[5:7]) - 1]} {int(iso[8:10])}"


def share(w):
    """The tags a shared link reads for its preview, in the same set the homepage uses."""
    title, text, alt = esc(w["page.title"]), esc(w["page.description"]), esc(w["page.share.alt"])
    return (f"<link rel='canonical' href='{LIVE}'><meta property='og:type' content='website'>"
            f"<meta property='og:url' content='{LIVE}'><meta property='og:site_name' content='ryansansbury.com'>"
            f"<meta property='og:title' content='{title}'><meta property='og:description' content='{text}'>"
            f"<meta property='og:image' content='{SHARE}'><meta property='og:image:width' content='1600'>"
            f"<meta property='og:image:height' content='838'><meta property='og:image:alt' content='{alt}'>"
            f"<meta name='twitter:card' content='summary_large_image'><meta name='twitter:title' content='{title}'>"
            f"<meta name='twitter:description' content='{text}'><meta name='twitter:image' content='{SHARE}'>")


def render(w, read_on=""):
    nav = w.table("ui.nav")
    tabs = w.table("ui.tab")
    views = "".join(f"<section class='view' id='v-{v}' data-view='{v}' tabindex='-1'></section>"
                    for v in ("map", "account", "score"))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='robots' content='index, follow'><meta name='referrer' content='no-referrer'>"
        f"<meta name='description' content='{esc(w['page.description'])}'>{share(w)}"
        f"<title>{esc(w['page.title'])}</title><link rel='icon' href='favicon.svg' type='image/svg+xml'>"
        "<link rel='stylesheet' href='app.css'></head><body>"
        f"<a class='skip' href='#main'>{esc(w['page.skip'])}</a>"
        "<header class='top'>"
        f"<a class='logo' href='#/map' data-go='map'>{MARK}<b>{esc(w['page.title'])}</b>"
        f"<span>{esc(w['page.subtitle'])}</span></a><div class='grow'></div>"
        "<span class='fresh' id='fresh'></span>"
        "<nav class='nav' aria-label='Views'>"
        f"<a href='#/map' data-go='map' data-nav='map'>{esc(nav['map'])}</a>"
        f"<a href='#/list' data-go='list' data-nav='list'>{esc(nav['list'])}</a>"
        f"<a href='#/how' data-go='how' data-nav='how'>{esc(nav['how'])}</a>"
        f"<button type='button' class='tourbtn' data-tour='0'>{esc(nav['tour'])}</button>"
        "</nav>"
        f"<button type='button' id='theme' class='theme' aria-pressed='false' aria-label='{esc(w['page.dark'])}' "
        f"title='{esc(w['page.dark'])}'>{THEME}</button></header>"
        "<p class='banner' id='banner' hidden></p>"
        f"<main id='main'><div class='strip' id='strip'>{views}</div>"
        "<section class='view' id='v-list' data-view='list' tabindex='-1'></section>"
        "<section class='view' id='v-how' data-view='how' tabindex='-1'></section></main>"
        "<nav class='tabbar' id='tabbar' aria-label='Screens'>"
        + "".join(f"<button type='button' data-tab='{k}'>{esc(v)}</button>" for k, v in tabs.items())
        + "</nav>"
        "<div class='tour' id='tour' role='dialog' aria-live='polite' hidden></div>"
        f"<footer class='foot'><p>{esc(w.fill('page.footer', date=long_date(read_on, w)))}</p></footer>"
        f"<noscript><p class='noscript'>{esc(w['page.noscript'])}</p></noscript>"
        + "".join(f"<script src='{s}'></script>" for s in SCRIPTS)
        + "</body></html>\n"
    )


def favicon():
    """The mark as the page's icon, so a browser never asks the site's root for one."""
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + MARK.replace('aria-hidden="true"', 'xmlns="http://www.w3.org/2000/svg"') + "\n"
