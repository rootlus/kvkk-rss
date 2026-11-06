"""Deterministic RSS and escaped, accessible static HTML."""
from datetime import date, datetime, time
from email.utils import format_datetime
from html import escape
import json
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from scripts.models import SOURCE_URL, sort_items

TITLE = "KVKK Veri İhlali Bildirimleri (Bağımsız RSS)"
DISCLAIMER = "KVKK ile bağlantısı olmayan bağımsız projedir."
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("atom", ATOM)


def rss_date(stamp):
    return format_datetime(datetime.fromisoformat(stamp.replace("Z", "+00:00")))


def render_feed(items, now, previous=None, limit=100, site_base_url=""):
    selected = sort_items(items)[:limit]
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    for name, value in [("title", TITLE), ("link", SOURCE_URL),
                        ("description", f"KVKK'nın kamuya açık veri ihlali duyuruları. {DISCLAIMER}"),
                        ("language", "tr-TR")]:
        ET.SubElement(channel, name).text = value
    build = ET.SubElement(channel, "lastBuildDate")
    build.text = rss_date(now)
    if site_base_url:
        parts = urlsplit(site_base_url)
        if parts.scheme != "https" or not parts.netloc or parts.query or parts.fragment or parts.username:
            raise ValueError("SITE_BASE_URL geçerli bir HTTPS site adresi olmalı")
        ET.SubElement(channel, f"{{{ATOM}}}link", {
            "href": site_base_url.rstrip("/") + "/feed.xml", "rel": "self", "type": "application/rss+xml"})
    for item in selected:
        node = ET.SubElement(channel, "item")
        ET.SubElement(node, "title").text = item.title
        ET.SubElement(node, "link").text = item.url
        ET.SubElement(node, "guid", {"isPermaLink": "false"}).text = item.id
        local_noon = datetime.combine(date.fromisoformat(item.published_date), time(12), ZoneInfo("Europe/Istanbul"))
        ET.SubElement(node, "pubDate").text = format_datetime(local_noon)
        ET.SubElement(node, "description").text = (
            f"{escape(item.title)} — Yayımlanma tarihi: {item.published_date}. Ayrıntılar için resmî KVKK duyurusunu ziyaret edin.")
    ET.indent(root, space="  ")

    def serialize():
        return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"

    if previous:
        old_root = ET.fromstring(previous)
        old_build = old_root.findtext("channel/lastBuildDate")
        if old_build:
            build.text = old_build
            if serialize() == previous:
                return previous
        build.text = rss_date(now)
    result = serialize()
    ET.fromstring(result)
    return result


def render_html(items, checked_at):
    rows = []
    for item in sort_items(items):
        rows.append(f'''<li class="announcement">
  <time datetime="{escape(item.published_date, quote=True)}">{date.fromisoformat(item.published_date).strftime('%d.%m.%Y')}</time>
  <h3><a href="{escape(item.url, quote=True)}">{escape(item.title)}<span aria-hidden="true"> ↗</span></a></h3>
  <span class="source">KVKK · Resmî duyuru</span>
</li>''')
    checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Istanbul"))
    return f'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="KVKK veri ihlali duyurularını bağımsız RSS akışıyla takip edin. Yalnızca başlık, tarih ve resmî bağlantı.">
<title>KVKK Veri İhlali Takip</title>
<link rel="alternate" type="application/rss+xml" title="KVKK Veri İhlali RSS" href="./feed.xml">
<link rel="stylesheet" href="./styles.css">
</head>
<body>
<a class="skip" href="#duyurular">Duyurulara geç</a>
<div class="shell">
<header class="topbar"><a class="brand" href="./"><span class="mark" aria-hidden="true">K/</span> VERİ İHLALİ TAKİP</a><a href="{SOURCE_URL}">Resmî kaynak ↗</a></header>
<main>
<section class="hero" aria-labelledby="page-title">
<p class="eyebrow">KAMUYA AÇIK BİLDİRİMLER · BAĞIMSIZ TAKİP</p>
<h1 id="page-title">KVKK Veri İhlali<br><span>Takip.</span></h1>
<p class="intro">Veri ihlali duyuruları, tek bir akışta.<br>Yeni bildirimleri RSS okuyucunuzdan takip edin.</p>
<a class="subscribe" href="./feed.xml"><span aria-hidden="true">◔</span> RSS'e abone ol <span aria-hidden="true">↗</span></a>
<p class="independent">{DISCLAIMER}</p>
</section>
<section class="listing" id="duyurular" aria-labelledby="list-title">
<div class="list-heading"><h2 id="list-title">Duyuru arşivi <span class="count">{len(items)}</span></h2><span>YENİDEN ESKİYE</span></div>
<p class="checked">Son başarılı tarama: <time datetime="{escape(checked_at, quote=True)}">{checked.strftime('%d.%m.%Y · %H:%M:%S')} (Europe/Istanbul)</time></p>
<ol class="announcements">{''.join(rows)}</ol>
</section>
<aside class="note"><strong>Açık kaynak. Asgari veri.</strong><p>Bu dizin yalnızca duyuru başlığı, yayın tarihi ve resmî bağlantıyı saklar. Duyuruların tam metni için KVKK sitesini ziyaret edin. Kaynaktan kaldırılan ilanların metaverisi arşivde korunur; bağlantıları çalışmayabilir.</p></aside>
</main>
<footer><span>{DISCLAIMER}</span><a href="./feed.xml">RSS akışı</a><a href="./status.json">Tarama durumu</a></footer>
</div>
</body>
</html>
'''.encode("utf-8")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
