# KVKK Veri İhlali Takip

KVKK'nın [kamuya açık veri ihlali bildirimlerini](https://www.kvkk.gov.tr/veri-ihlali-bildirimi) takip eden bağımsız Python projesi. Liste sayfalarından yalnızca **başlık, tarih ve resmî URL** toplar; kalıcı JSON arşivi, RSS 2.0 akışı ve mobil uyumlu statik HTML üretir. KVKK ile bağlantısı olmayan bağımsız projedir.

## Yerel kurulum

Python 3.12+ ve internet bağlantısı gerekir. Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/generate_feed.py --check-only
python scripts/generate_feed.py --bootstrap-pages 9
python -m http.server 8000 --directory docs
```

Windows'ta sanal ortamı `.venv\Scripts\activate` ile etkinleştirin. Siteyi `http://localhost:8000/`, akışı `http://localhost:8000/feed.xml` adresinde açın. Yalnızca statik dosyalar sunulur; web sunucusu veri toplamaz. Düzenli güncelleme:

```bash
python scripts/generate_feed.py --max-pages 5
python scripts/generate_feed.py --help
```

`--check-only` kaynak erişimini, robots kurallarını ve HTML parser'ını sınar; dosya oluşturmaz veya değiştirmez. `--bootstrap-pages` tarama derinliğini o çalışma için değiştirir. Arşiv her taramada korunur; bootstrap tekrar çalıştırılabilir. Eşzamanlı yerel üretim çalıştırmayın.

## Çıktılar

- `data/announcements.json`: sürüm 1 şeması; tüm toplanan duyurular ve değişmeyen `first_seen_at` UTC zamanı.
- `docs/feed.xml`: son 100 duyuru; sabit içerik kimliği, resmî bağlantı, güvenli özet.
- `docs/index.html`: tüm arşiv, duyuru tarihleri, RSS bağlantısı ve son başarılı kontrol zamanı.
- `docs/status.json`: UTC kontrol zamanı, toplam kayıt, o çalışmada yeni bulunan ve gözlenen kayıt sayıları. Bu dosya deploy'un başarılı olduğunu iddia etmez.
- `docs/styles.css` ve `.nojekyll`: statik sunum.

Başlık/tarih/URL değişiklikleri aynı kimlik altında güncellenir; önceki `first_seen_at` korunur. Kaynaktan kaybolan duyurular otomatik silinmez. Eşit tarihli kayıtlar kimliğe göre sıralanır. RSS'nin içeriği değişmediğinde XML dosyası **byte düzeyinde aynı kalır**, `lastBuildDate` yenilenmez. Feed sınırının dışındaki eski bir kaydın değişmesi RSS'yi etkilemez.

Kaynak saat belirtmediğinden RSS `pubDate` için yayın günü **12:00 Europe/Istanbul** kullanılır; bu gerçek yayın saati değildir. Sistem ve gözlem zamanları UTC'dir. HTML kontrol zamanını açıkça Europe/Istanbul etiketiyle gösterir.

**Durum güncelleme kararı:** Son başarılı kontrolün güncel görünmesi için HTML ve status her başarılı taramada yenilenir. Dolayısıyla yeni duyuru olmasa da saatlik bir commit/deploy oluşabilir; arşiv ve RSS değişmez. `last_seen_at` tutulmaz.

## GitHub Pages yayını

1. Dosyaları GitHub'da tercihen public bir repository'nin varsayılan branch'ine gönderin.
2. **Settings → Pages → Build and deployment → Source → GitHub Actions** seçin.
3. Repository/organizasyon politikasının workflow'a `contents: write`, `pages: write` ve `id-token: write` vermesine izin verdiğini kontrol edin. Branch koruması botun doğrudan commit göndermesini engelliyorsa uygun repository politikasını belirleyin.
4. `github-pages` environment kurallarının varsayılan branch'ten dağıtıma izin verdiğini kontrol edin.
5. **Actions → Update announcements and deploy Pages → Run workflow** ile varsayılan branch üzerinde başlatın. İlk geçmiş taraması için `bootstrap_pages` alanına `9` yazabilirsiniz.
6. Deploy adımının bildirdiği site adresini açın; `/feed.xml` yolunu RSS okuyucunuza ekleyin.

Workflow UTC `17 * * * *` ile saatte bir çalışır. Test, kaynak taraması veya commit/push başarısızsa artifact yayınlanmaz; önceki Pages yayını korunur. Uzak branch arada değişirse normal push güvenle reddedilir; force-push/rebase yapılmaz. Sonraki koşu en güncel branch'ten başlar. Yayın concurrency grubu eşzamanlı workflow'ları sıraya alır.

Pages artifact upload ve deploy aynı workflow'da açıkça çalışır; bot commit'inin ayrıca Pages build tetiklemesine ihtiyaç yoktur. Kurulum [GitHub'ın özel Pages workflow belgelerine](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) dayanır. PR testleri yalnızca okuma izni kullanır; yayın işi sadece schedule/manual ve varsayılan branch için çalışır.

Schedule kesin zaman garantisi vermez; GitHub işleri geciktirebilir ve hareketsiz public repository'lerde zamanlamayı devre dışı bırakabilir. [GitHub schedule davranışı](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

### Yayın sonrası kontrol

Gerçek site adresinizi kullanın:

```bash
curl --fail -I https://KULLANICI.github.io/REPO/feed.xml
curl --fail https://KULLANICI.github.io/REPO/feed.xml -o /tmp/published-feed.xml
python -c "from xml.etree import ElementTree as E; r=E.parse('/tmp/published-feed.xml').getroot(); assert r.tag == 'rss' and r.find('channel/item') is not None"
```

HTTP 200'ü ve XML'e uygun `Content-Type` başlığını kontrol edin; Pages MIME türünü uygulama kodu belirlemez. Telefon tarayıcısında ana sayfayı ve RSS bağlantısını açın; Feedly/Inoreader gibi bir okuyucuda aboneliği deneyin. Bu repository'nin yerel olarak oluşturulması tek başına public URL, başarılı Actions koşusu veya okuyucu kabulü anlamına gelmez.

## Ayarlar

CLI seçenekleri ilgili environment değerinden önce gelir; sayfa ve öğe sınırları pozitif tam sayı olmalıdır.

| Environment | Varsayılan | İşlev |
| --- | --- | --- |
| `KVKK_SOURCE_URL` | `https://www.kvkk.gov.tr/veri-ihlali-bildirimi` | Yalnızca KVKK liste adresi kabul edilir |
| `MAX_PAGES` | `5` | Düzenli sayfa sınırı |
| `MAX_FEED_ITEMS` | `100` | RSS öğe sınırı; arşivi sınırlamaz |
| `HTTP_TIMEOUT_SECONDS` | `15` | İstek timeout'u, pozitif saniye |
| `REQUEST_DELAY_SECONDS` | `1` | İstekler arası bekleme |
| `SITE_BASE_URL` | boş | HTTPS yayın adresi; varsa RSS self bağlantısı |
| `KVKK_USER_AGENT` | `kvkk-rss/1.0` | Actions repository adresini de ekler |

`--output-root` ile verileri farklı bir köke üretebilirsiniz; bu seçenek CSS'yi kopyalamaz, alternatif kökte `docs/styles.css` dosyasını ayrıca sağlayın. Kaynak URL'si, erişim kısıtlarını aşmak için kullanılamaz.

## Hata davranışı ve bakım

- 15 saniye istek timeout'u; ağ/500/502/503/504 için en fazla 2 yeniden deneme ve exponential backoff. 403/429 tekrar denenmez. HTTP yönlendirmeleri otomatik izlenmez.
- Önce `robots.txt` kontrol edilir. İzin vermiyorsa işlem durur; crawl-delay varsa uygulanır. 6 Kasım 2026 kontrolünde robots adresi ana sayfaya 302 döndürdü, kural dosyası sunulmadı. Yalnızca yokluk (404/410) veya ana sayfaya yönlendirme bu şekilde kabul edilir; erişim hataları işlemi durdurur.
- Gerçek HTML'deki `section.news .news__box .news__box-meta` yapısı kullanılır; tarih aynı karttan alınır. Fixtures 6 Kasım 2026'da alınan ilk iki sayfanın liste bölümleridir (görseller çıkarılmıştır).
- Liste konteyneri/kartlar kaybolursa, boş sayfa veya tamamen tekrar eden sayfa gelirse işlem hata verir. Son sayfa, boş HTML yerine sayfalama bağlantılarından belirlenir. Tek bir bozuk kayıt uyarıyla atlanır; bir sayfadaki kayıtların %20'sinden fazlası bozuksa koşu durur. Eksik tarihe güncel tarih atanmaz.
- Kaynak taraması ve render doğrulaması tüm dosya yazımlarından önce tamamlanır. Dosyalar aynı dizinde geçici dosyalara hazırlanıp `os.replace` ile atomik değiştirilir. Normal yazma hatasında önceki dosyalar geri yüklenir. Çok dosyalı işlem tek bir filesystem transaction değildir; işlem ortasında elektrik kesilirse yeniden çalıştırın. Actions başarısız koşuyu deploy etmez.
- Bozuk arşiv veya RSS üstüne sessizce yazılmaz. Git geçmişinden son geçerli dosyayı geri yükleyip sorunu inceleyin.
- Parser hatasında yeni HTML'yi inceleyin, fixtures ve parser'ı birlikte güncelleyin; boş akış yayımlayarak hatayı gizlemeyin.
- Son başarılı kontrolü `docs/status.json` ve Actions günlüklerinden izleyin. Actions başarısızlık bildirimlerini GitHub hesabınızdan açabilirsiniz.
- Bağımlılık ve action sürüm güncellemeleri için Dependabot yapılandırılmıştır. Action major etiketleri kullanılır; üretim politikanız gerektiriyorsa doğrulanmış commit SHA'larına sabitleyin.

## Testler

```bash
python -m pytest -q
```

Çevrimdışı testler gerçek liste fixture'larını, Türkçe ayları, URL sınırlarını, sayfalama/tekilleştirmeyi, arşiv sürekliliğini, değişmeyen RSS'yi, XML/HTML kaçışlamayı, check-only davranışını, robots engelini, HTTP/timeout hatalarını ve dosya yazma hatasında geri almayı kapsar. CI Python 3.12 ve 3.14 üzerinde aynı testleri çalıştırır. Canlı kaynak testi CI birim testlerinden ayrıdır; yayın workflow'u gerçek kaynağı tarar.

## Arşiv, düzeltme ve lisans

Tam metin, belge, kişisel veri ayrıntıları veya ihlal dokümanları indirilmez. Kaynaktan kaldırılan ilanların yalnızca başlık/tarih/URL metaverisi geçmişte korunur; bozuk bağlantılar olabilir. Hatalı metaveri veya kaldırma talebi için repository sahibiyle GitHub Issues üzerinden iletişime geçin; hassas kişisel veri eklemeyin. Repository sahibi talepleri değerlendirip gerekli düzeltmeyi ve gerekiyorsa Git geçmişi temizliğini yönetir. Kaynakta duran bir kaydın elle silinmesi sonraki taramada yeniden eklenmesine yol açar.

Kod [MIT](LICENSE) lisanslıdır. KVKK kaynak metaverisi ve fixture alıntıları üzerindeki haklar ilgili hak sahiplerine aittir; kod lisansı üçüncü taraf içeriğine yeniden kullanım izni vermez. Resmî hizmet değildir ve anlık bildirim garantisi sunmaz. Tasarım ayrıntıları: [BLUEPRINT.md](BLUEPRINT.md).
