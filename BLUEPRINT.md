# KVKK Veri İhlali RSS — Proje Blueprint'i

> **Durum:** Geliştirmeye hazır teknik tasarım · **Tarih:** 6 Kasım 2026  
> **Hedef:** KVKK'nın kamuya açık veri ihlali bildirimlerini otomatik takip etmek, geçmiş kayıtları korumak ve GitHub Pages üzerinden geçerli bir RSS 2.0 akışı ile basit bir statik arayüz yayımlamak.

## 1. Ürün özeti

**Proje adı:** `kvkk-rss` (çalışma adı)  
**Resmî kaynak:** https://www.kvkk.gov.tr/veri-ihlali-bildirimi  
**Çıktı:** `https://<github-kullanici>.github.io/kvkk-rss/feed.xml` (örnek; gerçek URL kullanıcı adına, repository adına ve Pages ayarlarına göre değişir).

Bir Python betiği KVKK'nın liste sayfasındaki yeni veri ihlali ilanlarını kontrol eder; doğrulanmış kayıtları JSON'da saklar; RSS XML ve kullanıcıya dönük HTML üretir. GitHub Actions bunu düzenli çalıştırır ve GitHub Pages'e dağıtır. **GitHub Pages'te sunucu tarafında scraping çalışmaz:** site yalnızca daha önce üretilmiş statik dosyaları sunar.

### Başarı ölçütleri

- RSS okuyucusuna eklenebilen, RSS 2.0 açısından geçerli ve herkese açık `feed.xml`.
- Yeni KVKK ilanı görüldüğünde kayıtların **tekilleştirilerek** eklenmesi.
- Aynı veri tekrar işlendiğinde RSS'nin semantik içeriğinin değişmemesi; yinelenen bildirim oluşmaması.
- Kaynağa erişim başarısızsa önceki başarılı yayın ve arşivin korunması.
- Herkese açık, mobil uyumlu, hafif bir ilan listesi (`index.html`).
- GitHub Actions'ta elle tetikleme ve zamanlanmış kontrol.
- Gizli anahtar, ücretli servis veya sürekli çalışan sunucu gerektirmemesi.

## 2. Kapsam

### MVP kapsamında

1. KVKK veri ihlali **liste sayfası** üzerinden duyuru başlığı, URL ve yayımlanma tarihini toplama.
2. Birden fazla sayfayı kontrol etme ve başlangıçta sınırlı bir tarihsel veri toplama (`bootstrap`).
3. Kalıcı duyuru arşivi tutma ve ilanları benzersiz içerik kimliğiyle ayırma.
4. RSS 2.0 oluşturma; doğru `guid`, `link`, `title`, `pubDate`, `description` alanları.
5. Statik HTML dizini oluşturma; duyuru başlıkları resmî kaynağa gider.
6. GitHub Actions ile zamanlanmış çalıştırma, değişiklikleri repo'ya kaydetme ve **aynı workflow içinde Pages'e açıkça deploy etme**.
7. Testler, hata günlükleri, README ve temel kullanım dokümantasyonu.

### MVP dışında

- KVKK ile resmî ortaklık veya resmî RSS hizmeti iddiası.
- Gerçek zamanlı/saniyelik bildirim garantisi.
- KVKK duyurularının tam metnini kalıcı olarak yeniden yayımlama.
- Kişisel veri içeren dokümanları indisleme veya ifşa etme.
- İleri seviye arama altyapısı, kullanıcı hesapları, ücretli bildirim hizmeti.

## 3. Doğrulanmış kaynak davranışı ve varsayımlar

6 Kasım 2026 itibarıyla gözlemlenen sayfa biçimi:

- Liste adresi: `https://www.kvkk.gov.tr/veri-ihlali-bildirimi`
- Sayfalama örneği: `https://www.kvkk.gov.tr/veri-ihlali-bildirimi?page=2`
- Duyuru bağlantısı örneği: `https://www.kvkk.gov.tr/Icerik/9092/kamuoyu-duyurusu-veri-ihlali-bildirimi-ncl-bahamas-ltd`
- Listede duyuru **başlığı** ve **Türkçe tarih** birlikte görünür.

Bu gözlemler mevcut davranıştır, **sabit bir API veya değişmez HTML sözleşmesi değildir**. Gerçek CSS seçicileri ve HTML öğe hiyerarşisi uygulama sırasında yeniden doğrulanmalıdır. Betik ilgili duyuruları, navigasyon bağlantılarından ayırmalı; beklenmedik şablon değişikliğinde sessizce boş RSS üretmemelidir.

**Kaynaklar:**
- https://www.kvkk.gov.tr/veri-ihlali-bildirimi
- https://www.kvkk.gov.tr/veri-ihlali-bildirimi?page=2
- https://www.kvkk.gov.tr/Icerik/9092/kamuoyu-duyurusu-veri-ihlali-bildirimi-ncl-bahamas-ltd

## 4. Mimari

```text
KVKK kamuya açık liste sayfaları
          |
          | HTTP GET (makul hız, timeout, retry)
          v
Python scraper / parser
          |
          | normalize + validate + deduplicate
          v
data/announcements.json  (kalıcı geçmiş)
          |
          +--> docs/feed.xml    (RSS 2.0)
          +--> docs/index.html  (statik arayüz)
          +--> docs/status.json (son başarılı kontrol bilgisi)
                    |
                    v
         GitHub Actions Pages deploy
                    |
                    v
               GitHub Pages
```

**Teknoloji tercihleri:** Python 3.12+, `requests`, `beautifulsoup4`, `feedgen` (veya stdlib ile XML), `pytest`, statik HTML/CSS. `lxml` isteğe bağlıdır. JavaScript framework'ü, veritabanı ve container zorunlu değildir.

## 5. Dosya ve klasör yapısı

```text
kvkk-rss/
├── .github/
│   └── workflows/
│       ├── update.yml             # Scrape + generate + commit + deploy
│       └── test.yml               # PR / push testleri (opsiyonel)
├── scripts/
│   ├── generate_feed.py           # CLI giriş noktası
│   ├── scraper.py                 # HTTP, pagination ve HTML parsing
│   ├── models.py                  # Veri modeli, tarih / URL işlemleri
│   └── render.py                  # RSS / HTML / status çıktıları
├── data/
│   └── announcements.json         # Kalıcı, sürümlenen kayıtlar
├── docs/
│   ├── .nojekyll
│   ├── feed.xml                   # Üretilen çıktı
│   ├── index.html                 # Üretilen çıktı
│   ├── status.json                # Üretilen çıktı
│   └── styles.css                 # Hafif, statik stil
├── tests/
│   ├── fixtures/
│   │   ├── list-page-1.html
│   │   ├── list-page-2.html
│   │   └── changed-layout.html
│   ├── test_scraper.py
│   ├── test_normalization.py
│   └── test_render.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
└── BLUEPRINT.md
```

## 6. Veri modeli ve kimliklendirme

`data/announcements.json` için önerilen kayıt biçimi:

```json
{
  "schema_version": 1,
  "items": [
    {
      "id": "kvkk-9092",
      "title": "Kamuoyu Duyurusu (Veri İhlali Bildirimi) – NCL (Bahamas) Ltd.",
      "url": "https://www.kvkk.gov.tr/Icerik/9092/kamuoyu-duyurusu-veri-ihlali-bildirimi-ncl-bahamas-ltd",
      "published_date": "2026-11-04",
      "first_seen_at": "2026-11-06T08:00:00Z",
      "last_seen_at": "2026-11-06T08:00:00Z"
    }
  ]
}
```

Yukarıdaki nesne **örnek şemadır**; `first_seen_at` ve `last_seen_at` değerleri gerçek gözlem verisi değildir.

- `id`: `/Icerik/<sayısal-id>/...` desenindeki sayısal içerik ID'sinden `kvkk-<id>` üret. Beklenmedik URL biçimi için kontrollü, deterministik URL hash'i kullan ve uyarı ver.
- `url`: KVKK alan adındaki kanonik mutlak URL. İzleme parametrelerini kaldır; üçüncü taraf linkleri reddet.
- `published_date`: Listedeki Türkiye yerel takvim tarihini `YYYY-MM-DD` biçimine dönüştür.
- `first_seen_at`: İlanın sistem tarafından ilk kez görüldüğü UTC zaman damgası; sonraki çalışmalarda değişmez.
- `last_seen_at`: Kayıt yeni taramada tekrar görülürse güncellenebilir; fakat sürekli değişen bu alan Git geçmişini ve deploy sayısını gereksiz artırabilir. **MVP'de her taramada güncellemek yerine bu alanı hiç tutmamak da kabul edilebilir.**
- Arşiv kayıtları silinmez; yalnızca gerçek içerik değişiklikleri ilgili alanları günceller. Aynı ID için başlık / tarih değişikliği yakalanır ve günlüklenir.
- Dosya UTF-8, kararlı anahtar sıralaması ve kararlı biçimlendirmeyle yazılır.

## 7. Scraper davranışı

### HTTP erişim politikası

- Tanımlı `User-Agent` (ör. `kvkk-rss/1.0 (+GitHub repository URL)`).
- İstek başına yaklaşık 10–20 saniye timeout, sınırlı retry + exponential backoff.
- `429`, `403` ve `5xx` durumlarında saldırgan biçimde yeniden deneme yapma; gerekiyorsa kontrolü başarısız say.
- KVKK'nın erişim koşullarını ve varsa `robots.txt` yönergelerini kontrol et; erişim yasaklarını aşma.
- Önerilen zamanlama **saatte bir**; daha sık kontrol gerçekten gerekliyse ayrıca değerlendir. Sayfalar arasında kısa gecikme kullan.
- İlan ayrıntılarını her çalışmada çekmek zorunlu değil; ilk sürüm liste sayfalarından üretilebilir.

### Sayfalama ve tarama

- `?page=1` yerine ilk sayfada kanonik URL kullan; sonraki sayfaları `?page=N` ile iste.
- Sayfa 1'den başla, ayarlanabilir `MAX_PAGES` sınırıyla tara (ilk öneri: 5).
- İlk kurulumda isteğe bağlı `--bootstrap-pages N` komutuyla daha fazla sayfayı tarayabil.
- Sonraki çalışmalarda sadece birkaç sayfayı kontrol et; geç yayımlanan / eski tarihli yeni kayıt ihtimalini azaltmak için sabit birden çok sayfa kontrolü yap.
- Sayfa tamamen boşsa bunun gerçek liste sonu mu yoksa HTML yapısı değişimi mi olduğunu ayırt et. İlk sayfada sıfır kayıt döndüğünde **hata üret ve mevcut çıktıyı koru**.
- Aynı ID'den yalnızca bir kayıt tutulur; mümkünse birden fazla sayfadaki çakışmaları da raporla.

### HTML parser

- Site genelindeki tüm bağlantıları almak yerine duyuru liste konteyneri içindeki `<a href="/Icerik/...">` bağlantılarını filtrele.
- Başlıkta `Veri İhlali Bildirimi` ifadesini yardımcı filtre olarak kullan, ama tek ve kırılgan seçim ölçütü yapma.
- Tarihi duyuruyla aynı kart / satır bağlamında ilişkilendir; üstteki veya alttaki duyurunun tarihini yanlış eşleştirme.
- Türkçe ay adları için açık eşleme: `Ocak`, `Şubat`, `Mart`, `Nisan`, `Mayıs`, `Haziran`, `Temmuz`, `Ağustos`, `Eylül`, `Ekim`, `Kasım`, `Aralık`.
- Hatalı tarih, bozuk URL veya eksik başlık için kaydı atla + günlükle; çok sayıda hata varsa koşuyu durdur.
- JavaScript gerekliliği tespit edilirse ilk tercih sitenin herkese açık veri isteğini araştırmak; tarayıcı otomasyonunu ancak gerekirse eklemek.

## 8. RSS 2.0 sözleşmesi

`docs/feed.xml` aşağıdaki özellikleri taşımalı:

| Alan | Kural |
| --- | --- |
| `channel/title` | `KVKK Veri İhlali Bildirimleri (Bağımsız RSS)` |
| `channel/link` | Resmî KVKK liste adresi |
| `channel/description` | Kaynağı ve bağımsızlık notunu açıklayan kısa metin |
| `channel/language` | `tr-TR` |
| `channel/lastBuildDate` | **Yalnızca yayımlanan feed içeriği değiştiğinde** güncellenmeli |
| `item/title` | İlanın özgün başlığı |
| `item/link` | Resmî duyuru bağlantısı |
| `item/guid` | `isPermaLink="false"` ile sabit `kvkk-<id>` |
| `item/pubDate` | KVKK'nın yayımlanma tarihi; günün kesin saati bilinmiyorsa tarih `Europe/Istanbul` yerel saatinde 12:00 kabul edilerek RFC 822/2822'ye çevrilir ve bu yaklaşım belgelenir |
| `item/description` | Kısa, güvenli özet: ilan başlığı + resmî kaynağa yönlendirme; tam metin yok |

- RSS tarihlerini `Europe/Istanbul` ile işle; sistem zamanı ve ilk görülme UTC'de tutulabilir.
- RSS öğeleri yayımlanma tarihine göre yeni → eski sıralanır; eşit tarihlerde deterministik ID sıralaması kullanılır.
- `MAX_FEED_ITEMS` için önerilen başlangıç değeri 100; kalıcı `announcements.json` daha fazla kayıt içerebilir.
- Üretim XML-escape yapmalı; `&`, `<`, `>` ve Unicode Türkçe karakterler XML'i bozmamalı.
- İçeriği tekrar üretilen `feed.xml`, değişiklik yoksa byte düzeyinde aynı kalmalı.
- Dosya `application/rss+xml; charset=utf-8` olarak servis edilebilmesi hedeflenir. GitHub Pages'in MIME türü davranışı doğrulanmalı; istemcinin XML'i okuyabilmesi ayrıca test edilmeli.

## 9. Statik web arayüzü

`docs/index.html` hafif bir dizin olsun:

- Başlık: **KVKK Veri İhlali Takip**.
- Belirgin **RSS'e abone ol** bağlantısı (`./feed.xml`).
- Resmî kaynak bağlantısı ve **"KVKK ile bağlantısı olmayan bağımsız projedir"** açıklaması.
- Güncel duyuru başlığı, yayımlanma tarihi ve KVKK'ya giden bağlantı.
- Son başarılı tarama zamanı (UTC ya da açıkça `Europe/Istanbul` etiketiyle).
- Mobil uyumlu, klavyeyle erişilebilir, yüksek kontrastlı, düşük bağımlılıklı tasarım.
- Başlıklarda HTML kaçışlama; kaynak metin asla güvenilmeyen HTML olarak eklenmemeli.
- `<link rel="alternate" type="application/rss+xml" title="KVKK Veri İhlali RSS" href="./feed.xml">` etiketini `<head>` içine koy.
- İsteğe bağlı istemci tarafı arama / filtreleme sonraki sürüme bırakılabilir.

## 10. GitHub Actions ve Pages yayın stratejisi

**Kritik karar:** GitHub Pages yayını için **Source = GitHub Actions** seç. Aynı `update.yml` içinde yeni statik dosyaları ürettikten sonra Pages artifact'ini yükle ve açıkça deploy et.

> **Neden?** GitHub'ın dokümantasyonuna göre `GITHUB_TOKEN` ile workflow'un yaptığı commit, tek başına `Deploy from a branch` tabanlı Pages build'ini tetiklemeyebilir. Bu nedenle yalnızca `git push`'a güvenilmemeli. Kaynak: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

### İş akışı tasarımı

1. `schedule` ile varsayılan branch üzerinde saatte bir çalış (`17 * * * *` gibi, UTC); `workflow_dispatch` ile elle çalıştırılabilsin.
2. `permissions`: en az `contents: write`, `pages: write`, `id-token: write` (commit + Pages deploy için).
3. `concurrency`: tek bir yayın koşusunun diğerinin üzerine yazmasını önle; `cancel-in-progress: false` tercih et.
4. `actions/checkout` → Python kurulumu → bağımlılıkların yüklenmesi → test / doğrulama → scraper ve renderer.
5. Geçersiz / boş kaynak sonucu varsa koşuyu başarısız bitir; önceki dosyaları silme / değiştirme.
6. Değişen `data/announcements.json` ve `docs/` çıktıları için kontrollü commit yap, ardından `git push`. Yeni içerik yoksa commit oluşturma.
7. `actions/configure-pages` → `actions/upload-pages-artifact` (`path: ./docs`) → `actions/deploy-pages` ile **aynı çalışmada** yayımla.
8. Repo ayarlarında **Settings → Pages → Build and deployment → Source: GitHub Actions** seç.
9. İlk Pages dağıtımı için gerekli repo izinleri / environment `github-pages` kurallarını kontrol et. PR kodları üzerinden secret veya yazma yetkili iş akışı çalıştırma.

**Yarış koşulu notu:** `git push` öncesinde uzak branch değişmişse kontrollü tekrar deneme veya güvenli abort kullan; force-push yapma. `concurrency` aynı workflow'un eşzamanlı çalışmasını azaltır ancak insan tarafından yapılan commitleri engellemez.

**Önemli GitHub davranışı:** Zamanlanmış işler tam zamanında başlamak zorunda değildir, yoğunlukta gecikebilir / atlanabilir. Public repo'da uzun süre aktivite yoksa schedule devre dışı kalabilir. Workflow'un varsayılan branch'te bulunduğunu kontrol et. Kaynak: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

## 11. Hata yönetimi ve gözlemlenebilirlik

- HTTP timeout / 5xx: sınırlı retry; nihai başarısızlıkta eski RSS ve JSON yerinde kalır.
- `403` / `429`: siteye yüklenme veya kısıt riskine karşı aşırı retry yapma.
- Beklenmeyen HTML / 0 kayıt: fail closed; **boş RSS ile üstüne yazma**.
- Hatalı tarih: doğrulama hatasını logla; sahte `pubDate` uydurma.
- Eksik yayın tarihi: ilk MVP'de kaydı hatalı saymak veya `pubDate` olmadan sunmak arasında bir politikayı belirle; sessizce güncel tarih atama.
- XML / JSON bozukluğu: atomik dosya yazımı (`tempfile` + `os.replace`) ve parse-back doğrulaması.
- `docs/status.json` içinde son başarılı tarama zamanı, son başarılı deploy'a aday üretim zamanı, toplam duyuru sayısı, son çalışmada bulunan yeni duyuru sayısı tutulabilir. Her çalışmada zaman damgası değişirse gereksiz commit / deploy doğacağını bil; yalnızca başarılı kontrolde güncelleme sıklığını sınırlamak veya statü dosyasını her çalışmada commit etmeyi tercih etmek bilinçli bir ürün kararı olmalı.
- GitHub Actions hata verdiğinde repository sahibi Actions ekranından görebilmeli; isteğe bağlı başarısızlık e-posta bildirimi GitHub ayarlarından yönetilebilir.

## 12. Güvenlik, etik ve içerik politikası

- Yalnızca **kamuya açık** ilan başlığı, tarih ve URL gibi asgari metaverileri sakla.
- KVKK sayfasını, engelleri, CAPTCHA'yı veya giriş kontrollerini aşmaya çalışma.
- KVKK'nın resmî RSS servisi izlenimi verme; tüm sayfalarda açık bağımsızlık notu bulunsun.
- İçeriği resmî kaynakta değişmiş / kaldırılmış ilanlar için arşiv politikası açık olsun. **Geçmiş duyurulara ait sadece başlık-tarih-URL metaverisini sakla**; kaldırılan duyurular için bağlantı çalışmayabilir. Kaynağın kaldırılmasını görmezden gelmenin hukuki/etik sonuçları değerlendirilmeli; gerekirse takedown / düzeltme kanalı sağlanmalı.
- Kişisel verileri veya ihlal detayındaki hassas bilgileri otomatik kopyalama.
- Üçüncü taraf JS / analytics zorunlu değil; kullanırsan gizlilik etkisini değerlendir.
- HTML çıktısını kaçışla; URL'leri `https://www.kvkk.gov.tr` alan adıyla sınırla.
- GitHub Actions bağımlılıklarını ve action sürümlerini düzenli güncelle; mümkünse production workflow'da commit SHA ile pinle.

## 13. Test planı

**Birim testleri**

- Türkçe tarih dönüştürme: `4 Kasım 2026, Çarşamba` → `2026-11-04`.
- `/Icerik/9092/...` → `kvkk-9092`, URL normalization.
- Ayrı sayfalarda yinelenen ilanlar için deduplication.
- Eşit tarihli kayıtların deterministik sıralanması.
- Türkçe karakterler, `&`, `<`, `>` için geçerli RSS/HTML escaping.
- İkinci kez aynı girdiyle çalışmada duplicate olmaması.

**Fixture / entegrasyon testleri**

- En az iki gerçekçi HTML fixture (sayfa 1 ve sayfa 2).
- Sayfa düzeni değişmiş fixture'da parser'ın sessizce boş veri döndürmeyip hata üretmesi.
- 404, 429, 500, timeout simülasyonları.
- Boş sonuç halinde önceki `feed.xml` ve JSON'un korunması.
- Oluşturulan XML'in standart XML parser'ı ile yeniden okunabilmesi.
- Yeni veri yoksa `feed.xml` byte içeriğinin değişmemesi.

**Canlı smoke test**

- `python scripts/generate_feed.py --check-only` kaynağa salt-okunur erişimi sınar.
- İlk başarılı Actions koşusu ve Pages yayını sonrası `feed.xml` HTTP 200, parsable RSS, en az 1 gerçek duyuru.
- `index.html` mobil tarayıcıda açılır ve RSS linki çalışır.
- Feedly / Inoreader gibi bir okuyucu gerçek feed'i kabul eder (manuel test).

## 14. CLI ve konfigürasyon

Önerilen komutlar:

```bash
python scripts/generate_feed.py --check-only
python scripts/generate_feed.py --bootstrap-pages 9
python scripts/generate_feed.py --max-pages 5
pytest -q
```

Önerilen environment değişkenleri:

| Değişken | Varsayılan | Açıklama |
| --- | --- | --- |
| `KVKK_SOURCE_URL` | `https://www.kvkk.gov.tr/veri-ihlali-bildirimi` | Kaynak liste sayfası |
| `MAX_PAGES` | `5` | Düzenli tarama derinliği |
| `MAX_FEED_ITEMS` | `100` | RSS'deki en fazla kayıt |
| `HTTP_TIMEOUT_SECONDS` | `15` | İstek zaman aşımı |
| `REQUEST_DELAY_SECONDS` | `1` | Liste sayfaları arasındaki alt gecikme |
| `SITE_BASE_URL` | Kullanıcıya ait Pages URL | Feed için opsiyonel öz bağlantı |

`--check-only`, hiçbir çıktı dosyasına yazmamalıdır. `--bootstrap-pages` ilk kurulumda geçmiş sayfaları toplamalıdır. Tüm seçeneklerde `--help` dokümanı bulunmalıdır.

## 15. Uygulama aşamaları

### Faz 1 — Kaynak toplama
- [ ] Sayfanın güncel HTML yapısını incele, sağlam CSS seçicilerini belirle.
- [ ] Liste ve sayfalama parser'ını geliştir.
- [ ] Veri doğrulama, tarihler ve ID normalizasyonunu ekle.
- [ ] Fixture tabanlı parser testlerini yaz.

### Faz 2 — Kalıcı veri ve RSS
- [ ] JSON veri modelini oluştur.
- [ ] Deduplication + bootstrap + güvenli atomik yazımı ekle.
- [ ] RSS 2.0 üret ve XML testlerini tamamla.
- [ ] Değişmeyen girdiyle kararlı çıktı üretimini doğrula.

### Faz 3 — Statik yayın
- [ ] Basit ve erişilebilir `index.html` / `styles.css` hazırla.
- [ ] Resmî kaynak bağlantıları, RSS aboneliği ve bağımsızlık notunu ekle.
- [ ] `docs/.nojekyll` ve gerekirse `status.json` oluştur.

### Faz 4 — GitHub otomasyonu
- [ ] `update.yml` içinde schedule + manual trigger ekle.
- [ ] Commit yalnızca değişiklik varsa yapılsın.
- [ ] Pages Source = GitHub Actions yapılandır.
- [ ] Pages artifact upload + explicit deploy adımlarını ekle.
- [ ] İlk manuel workflow ve gerçek URL smoke testini gerçekleştir.

### Faz 5 — Kalite ve bakım
- [ ] README: kurulum, yerel çalıştırma, Pages yayını, sorun giderme.
- [ ] Hata durumlarında mevcut feed'in korunduğunu test et.
- [ ] Makul trafik, robots/erişim ilkeleri ve arşiv politikasını gözden geçir.
- [ ] Dependabot / bağımlılık güncellemeleri (isteğe bağlı).

## 16. Definition of Done (kabul kriterleri)

Proje tamamlandı sayılabilmesi için:

1. `feed.xml` public URL'den açılıyor ve XML/RSS olarak parse ediliyor.
2. Akış en az bir gerçek KVKK veri ihlali ilanını doğru başlık, URL ve tarihle içeriyor.
3. İki ardışık çalışmada aynı duyuru ikinci kez eklenmiyor.
4. Daha önceki kayıtlar, kaynaktan kaybolduklarında otomatik silinmiyor.
5. KVKK erişimi kapalıyken veya HTML değiştiğinde önceki başarılı veri bozulmuyor.
6. Workflow otomatik ve manuel olarak tetiklenebiliyor.
7. Actions'ın yaptığı commit'e bağlı olmayan, açıkça tanımlanmış Pages deploy adımı var.
8. Statik ana sayfada abonelik linki ve "resmî değildir" açıklaması mevcut.
9. En az temel parser/RSS testleri CI üzerinde geçiyor.
10. README'de operasyon, limitler ve bilinen riskler anlatılıyor.

## 17. Açık kararlar ve önerilen varsayılanlar

| Konu | Önerilen karar |
| --- | --- |
| Lisans | MIT (kod için); KVKK içeriği için ayrıca telif/yeniden kullanım notu |
| Repository görünürlüğü | Public |
| Güncelleme aralığı | Saatte bir, `17 * * * *` UTC |
| İlk geçmiş taraması | 9 sayfaya kadar, sonra 5 sayfa |
| Feed uzunluğu | Son 100 ilan |
| İçerik kapsamı | Başlık + tarih + resmî bağlantı |
| Veri saklama | Git'te sürümlenen JSON |
| Yayınlama | GitHub Actions Pages deployment (branch build'e bağlı değil) |
| Arayüz | Vanilla HTML/CSS, istemci JS zorunlu değil |
| Tarih saat hassasiyeti | Kaynakta saat yoksa ilan tarihine sabit 12:00 İstanbul saati |

## 18. Kaynaklar ve referanslar

- KVKK veri ihlali bildirimleri: https://www.kvkk.gov.tr/veri-ihlali-bildirimi
- KVKK ikinci sayfa: https://www.kvkk.gov.tr/veri-ihlali-bildirimi?page=2
- GitHub Pages yayın kaynağı ve `GITHUB_TOKEN` davranışı: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- GitHub Actions zamanlanmış işler: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- RSS 2.0 belirtimi: https://www.rssboard.org/rss-specification

---

### Proje uygulama talimatı (AI coding agent / geliştirici için)

Bu blueprint'i uygularken önce HTML fixture'ları ve kaynak parser'ını doğrula. Gerçek KVKK HTML yapısını görmeden CSS seçicisi uydurma. Kaynak başarısızlığında arşiv veya RSS dosyasını sıfırlama. GitHub Pages'i `GITHUB_TOKEN` ile yapılan commit'in otomatik tetikleyeceğini varsayma; Pages deploy'u aynı workflow içinde açıkça çalıştır. Kod, dokümantasyon ve testleri tamamla; gerçek bir site adresi veya canlı çalışma başarısı doğrulanmadan bunları gerçekleşmiş olarak raporlama.
