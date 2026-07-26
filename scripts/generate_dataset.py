#!/usr/bin/env python3
"""Generate the Turkish Daily Dialogues 5K release artifacts.

The corpus is composed from a repository-owned Turkish scenario library drafted
with AI assistance.  Release generation itself is deterministic: no network,
model inference, scraped corpus, or runtime clock is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATASET_VERSION = "1.0.0"
GENERATOR_VERSION = "1.0.0"
SEED = 20260726
RECORD_COUNT = 5_000
SCENARIO_FAMILIES_PER_TOPIC = 38
TRAIN_FAMILIES_PER_TOPIC = 30
VALIDATION_FAMILIES_PER_TOPIC = 4
TEST_FAMILIES_PER_TOPIC = 4


@dataclass(frozen=True)
class TopicSpec:
    slug: str
    title: str
    setting: str
    # Deliberately topic-level and broad: every descriptor must remain true for
    # every core/addon recombination in that topic.
    relationships: tuple[str, ...]
    formality: str
    cores: tuple[tuple[str, str, str, str], ...]
    addons: tuple[tuple[str, str], ...]


def topic(
    slug: str,
    title: str,
    setting: str,
    relationships: tuple[str, ...],
    formality: str,
    cores: list[tuple[str, str, str, str]],
    addons: list[tuple[str, str]],
) -> TopicSpec:
    return TopicSpec(slug, title, setting, relationships, formality, tuple(cores), tuple(addons))


TOPICS: tuple[TopicSpec, ...] = (
    topic(
        "market-alisverisi",
        "Market alışverişi",
        "mahalle marketi",
        ("müşteri-market çalışanı",),
        "polite",
        [
            (
                "Bugünkü yemek için taze sebze bakıyorum.",
                "Tezgahta bu sabah gelen ürünler var.",
                "Domateslerin biraz sert olanlarından seçebilir miyiz?",
                "Elbette, yemeklik olanları ayırabilirim.",
            ),
            (
                "Bu ürünün daha küçük paketi var mı?",
                "Aynı markanın yarım kiloluk paketi alt rafta.",
                "İçeriğinde ilave şeker bulunuyor mu?",
                "Etikete göre ilave şeker içermiyor.",
            ),
            (
                "Alışveriş listesindeki pirinci bulamadım.",
                "Bakliyat reyonunun en sonunda, sağ tarafta.",
                "Bir de bulgur aynı bölümde mi?",
                "Evet, hemen yanındaki rafta.",
            ),
            (
                "Kasaya geçmeden indirimli ürünleri kontrol etmek istiyorum.",
                "Turuncu etiketli olanlar bu haftanın indiriminde.",
                "İndirim kasada otomatik uygulanıyor mu?",
                "Evet, üyelik gerektirmeden uygulanıyor.",
            ),
            (
                "Bu ekmek bugün mü çıktı?",
                "Evet, sabahki ilk üretimden.",
                "Dilimletebilir miyim?",
                "Tabii, fırın bölümünde hemen dilimletebiliriz.",
            ),
            (
                "İki kişilik kahvaltı için ne kadar peynir yeterli olur?",
                "Yaklaşık üç yüz gram genelde yeterli oluyor.",
                "Az tuzlu olanından alayım o zaman.",
                "Az tuzlu çeşidi şu kapta, tadına da bakabilirsiniz.",
            ),
            (
                "Bez çantamı evde unutmuşum.",
                "Kâğıt çanta ve yeniden kullanılabilir çanta seçeneklerimiz var.",
                "Kâğıt olan yeterli olur.",
                "Tamam, ürünleri ona yerleştiririm.",
            ),
            (
                "Fişte bir ürünü iki kez geçmiş olabilir miyiz?",
                "Birlikte kontrol edelim; hangi üründü?",
                "Yoğurt satırında iki adet görünüyor ama bir tane aldım.",
                "Haklısınız, fazla kaydı şimdi düzeltiyorum.",
            ),
        ],
        [
            ("Poşet yerine kutu kullanabilir miyiz?", "Uygun bir karton kutu getirebilirim."),
            ("Ödemeyi iki karta bölebilir miyim?", "Evet, tutarı istediğiniz gibi bölebiliriz."),
            ("Yoğun olmayan bir kasa var mı?", "Arka taraftaki kasa şu an daha sakin."),
            ("Ürünü açmadan son kullanma tarihine bakalım mı?", "Tabii, tarih paketin yan yüzünde yazıyor."),
            ("Eksik kalanları sonra tekrar alırım.", "İsterseniz listeyi fişin arkasına not edebilirsiniz."),
            ("Bu reyon saat kaça kadar açık kalıyor?", "Market kapanana kadar hizmet veriyor."),
        ],
    ),
    topic(
        "kafe-bulusmasi",
        "Kafede buluşma",
        "semt kafesi",
        ("kafede buluşan tanışıklar",),
        "informal",
        [
            (
                "Ben biraz erken geldim, pencere kenarına oturdum.",
                "Harika, ben de beş dakikaya oradayım.",
                "Senin için bir şey söyleyeyim mi?",
                "Sade bir filtre kahve söylersen çok iyi olur.",
            ),
            (
                "Bugün hangi kafede buluşuyoruz?",
                "Parkın karşısındaki küçük kafeyi düşündüm.",
                "Orası öğleden sonra çok kalabalık oluyor mu?",
                "Genelde sakin; arka bahçede de yer var.",
            ),
            (
                "Toplantıdan çıktım, biraz gecikeceğim.",
                "Sorun değil, acele etme.",
                "On dakika içinde gelebilirim.",
                "Tamam, ben menüye bakarım.",
            ),
            (
                "Kahvenin yanında bir şey paylaşalım mı?",
                "Limonlu kek güzel görünüyordu.",
                "Çok tatlı değilse onu deneyebiliriz.",
                "Garsona sorup bir dilim söyleyelim.",
            ),
            (
                "Laptopla çalışabileceğimiz bir masa buldun mu?",
                "Prizin yanındaki büyük masa boş.",
                "İnternet bağlantısı da iyi mi?",
                "Geçen sefer sorunsuz kullanmıştım.",
            ),
            (
                "Dışarıda mı, içeride mi oturalım?",
                "Hava serinledi; içerisi daha rahat olur.",
                "Kapıya yakın olmayan bir yer seçelim.",
                "Tamam, üst kattaki masalara bakalım.",
            ),
            (
                "Bu kez farklı bir içecek denemek istiyorum.",
                "Soğuk demleme kahveleri güzel olabilir.",
                "Süt eklemeden içsem sert gelir mi?",
                "Tadımlık küçük boyla başlayabilirsin.",
            ),
            (
                "Hesabı ayrı ödeyelim mi?",
                "Bence kolaylık olur, ayrı ödeyelim.",
                "Kasada mı söylüyoruz?",
                "Evet, masa numarasını verince ayırıyorlar.",
            ),
        ],
        [
            ("Müzik biraz yüksek olursa üst kata geçeriz.", "Olur, orası genelde daha sessiz."),
            ("Çıkışta kısa bir yürüyüş yapalım mı?", "Vaktimiz kalırsa parka uğrayalım."),
            ("Bugünkü planı çok uzatmayalım.", "Tamam, bir saat bize yeter."),
            ("Menüde bitkisel süt seçeneği var mıydı?", "Badem ve yulaf sütü vardı diye hatırlıyorum."),
            ("Masaya su da isteyelim.", "Garson gelince ben söylerim."),
            ("Dönüşte aynı yöne gidecek miyiz?", "Metro girişine kadar beraber yürürüz."),
        ],
    ),
    topic(
        "restoran-rezervasyonu",
        "Restoran rezervasyonu",
        "yerel restoran",
        ("müşteri-restoran çalışanı",),
        "polite",
        [
            (
                "Yarın akşam için iki kişilik masa ayırtmak istiyorum.",
                "Saat kaç civarı gelmeyi düşünüyorsunuz?",
                "Yedi buçuk bizim için uygun.",
                "O saatte içeride bir masamız müsait.",
            ),
            (
                "Hafta sonu ailece geleceğiz; dört kişilik yeriniz var mı?",
                "Cumartesi öğlen için yerimiz bulunuyor.",
                "Çocuk sandalyesi de rica edebilir miyiz?",
                "Elbette, rezervasyona ekliyorum.",
            ),
            (
                "Rezervasyon saatini biraz öne çekebilir miyiz?",
                "Mevcut kaydı kontrol ediyorum.",
                "Yarım saat erken gelmemiz yeterli.",
                "Altı buçuk için güncelledim.",
            ),
            (
                "Bahçede boş masa olup olmadığını öğrenebilir miyim?",
                "Hava durumuna bağlı olarak bahçeyi açık tutuyoruz.",
                "Kapalı olursa cam kenarı da uygun.",
                "Bu tercihi rezervasyon notuna ekledim.",
            ),
            (
                "Grubumuzdan bir kişi gelemeyecek.",
                "Kişi sayısını kaç olarak güncelleyelim?",
                "Beş yerine dört kişi olacağız.",
                "Rezervasyonu dört kişi olarak düzenledim.",
            ),
            (
                "Menüde vejetaryen seçenek bulunuyor mu?",
                "Başlangıç ve ana yemeklerde birkaç seçeneğimiz var.",
                "Rezervasyona bu tercihi not eder misiniz?",
                "Tabii, mutfak ekibine iletilecek.",
            ),
            (
                "Özel bir gün için sakin bir masa arıyoruz.",
                "Arka salondaki köşe masalar daha sakin.",
                "Mümkünse oradan ayırabilir misiniz?",
                "Uygunluk durumuna öncelikli not düşüyorum.",
            ),
            (
                "Rezervasyonu iptal etmem gerekiyor.",
                "Tarih ve saati doğrulayabilir miyiz?",
                "Pazar günü saat sekizdeydi.",
                "Kaydı iptal ettim, yeni bir ödeme oluşmayacak.",
            ),
        ],
        [
            ("Masada alerjen listesini de görebilir miyiz?", "Evet, güncel listeyi servis ekibi getirebilir."),
            ("Gecikirsek ne kadar bekletebilirsiniz?", "On beş dakikaya kadar masayı koruyoruz."),
            ("Otopark konusunda bilgi verebilir misiniz?", "Yakındaki kapalı otoparkla anlaşmamız var."),
            ("Pastayı dışarıdan getirmek mümkün mü?", "Önceden haber verirseniz kabul ediyoruz."),
            ("Sessiz bir bölüm tercih ediyoruz.", "Notunuza ekliyorum; uygun masayı seçeriz."),
            ("Rezervasyon için kapora gerekiyor mu?", "Bu kişi sayısı için kapora almıyoruz."),
        ],
    ),
    topic(
        "evde-yemek",
        "Evde yemek hazırlama",
        "ev mutfağı",
        ("aynı evde yaşayan yakınlar",),
        "informal",
        [
            (
                "Akşam ne pişirelim?",
                "Fırında sebze ve yanında pilav yapabiliriz.",
                "Sebzeleri ben doğrayayım mı?",
                "Olur, ben de pilavı hazırlarım.",
            ),
            (
                "Çorbanın tuzu biraz az olmuş.",
                "Servisten önce biraz daha ekleyebiliriz.",
                "Önce küçük bir kâsede deneyelim.",
                "İyi fikir, tadını bozma riskimiz olmaz.",
            ),
            (
                "Evde yumurta kalmış mı?",
                "Dolapta dört tane gördüm.",
                "Kahvaltıya omlet yapmaya yeter.",
                "Yanına domates de doğrarız.",
            ),
            (
                "Tarifte iki bardak un yazıyor ama az kaldı.",
                "Bir buçuk bardak var gibi görünüyor.",
                "Ölçüyü küçültüp yapalım o zaman.",
                "Diğer malzemeleri de aynı oranda azaltırız.",
            ),
            (
                "Yemek biraz geç hazır olacak.",
                "Ben masayı kurup salatayı yaparım.",
                "Ekmek almayı da unuttuk.",
                "Ben aşağı inip hemen alabilirim.",
            ),
            (
                "Dünden kalan yemeği değerlendirelim mi?",
                "Isıtıp yanına yoğurt ekleyebiliriz.",
                "Önce kokusunu ve görünümünü kontrol edelim.",
                "Uygunsa iyice ısıtırız.",
            ),
            (
                "Tatlı için kolay bir şey yapalım.",
                "Meyveli yoğurt hazırlamak hızlı olur.",
                "Muz ve elma var mı?",
                "İkisi de var, biraz tarçın da ekleriz.",
            ),
            (
                "Mutfak çok dağıldı.",
                "Yemek pişerken tezgâhı toparlayalım.",
                "Ben bulaşıkları sudan geçiririm.",
                "Ben de malzemeleri dolaba kaldırırım.",
            ),
        ],
        [
            ("Artanı yarın için saklayalım.", "Soğuyunca kapaklı bir kaba koyarız."),
            ("Fırını önceden açtın mı?", "Evet, uygun sıcaklığa gelmek üzere."),
            ("Baharatı herkes kendi tabağına eklesin.", "Böylece tadı herkes ayarlayabilir."),
            ("Porsiyonları çok büyük yapmayalım.", "Önce az koyar, isteyen olursa ekleriz."),
            ("Yemekten sonra çay demleyelim.", "Suyu şimdiden ocağa koyabilirim."),
            ("Tarifi bir yere not edelim.", "Beğenirsek mutfak defterine yazarız."),
        ],
    ),
    topic(
        "toplu-tasima",
        "Toplu taşımayla yolculuk",
        "otobüs ve metro ağı",
        ("yolcu-ulaşım bilgisi sağlayan kişi",),
        "polite",
        [
            (
                "Merkeze gitmek için hangi otobüse binmeliyim?",
                "Bu duraktan geçen on numaralı hat doğrudan gidiyor.",
                "Yaklaşık ne kadar sürer?",
                "Trafiğe göre yarım saat kadar sürüyor.",
            ),
            (
                "Bu metro havalimanı yönüne gidiyor mu?",
                "İki durak sonra aktarma yapmanız gerekiyor.",
                "Aktarma aynı istasyonda mı?",
                "Evet, tabelaları izleyerek alt kata ineceksiniz.",
            ),
            (
                "Kartım turnikede okunmadı.",
                "Bakiyeyi cihazdan kontrol edebiliriz.",
                "Yeterli bakiye görünüyor.",
                "Kartı düz tutup yeniden deneyelim.",
            ),
            (
                "Son otobüsün saatini öğrenebilir miyim?",
                "Hafta içi son sefer gece yarısından biraz önce.",
                "Bugün hafta sonu tarifesi mi geçerli?",
                "Hayır, bugün normal tarife uygulanıyor.",
            ),
            (
                "Bebek arabasıyla hangi giriş daha uygun?",
                "Asansörlü giriş caddenin diğer tarafında.",
                "Perona doğrudan iniyor mu?",
                "Evet, ara katta tekrar asansör değiştiriyorsunuz.",
            ),
            (
                "Bu durakta ne kadar bekleyeceğiz?",
                "Ekrana göre araç altı dakika sonra geliyor.",
                "Yoğunluk bilgisi de görünüyor mu?",
                "Bir sonraki araç orta yoğunlukta görünüyor.",
            ),
            (
                "Yanlış yöndeki trene bindim sanırım.",
                "Bir sonraki durakta inip karşı perona geçebilirsiniz.",
                "Ek ücret kesilir mi?",
                "İstasyondan çıkmadığınız sürece kesilmez.",
            ),
            (
                "Bisikletle metroya binebilir miyim?",
                "Yoğun saatler dışında son vagonda izin veriliyor.",
                "Şu an uygun saat aralığında mıyız?",
                "Evet, fakat son vagonu kullanmanız gerekiyor.",
            ),
        ],
        [
            ("Durak anonslarını duymakta zorlanıyorum.", "Kapı üstündeki ekrandan da takip edebilirsiniz."),
            ("İnerken düğmeye basmam gerekir mi?", "Bu hatta durak talebi için düğmeye basılıyor."),
            ("Kartı nereden doldurabilirim?", "İstasyon girişindeki cihazlar açık."),
            ("Aktarma süresi uzun mu?", "Yürüyüşle birlikte yaklaşık sekiz dakika."),
            ("Araçta kayıp eşya bürosu bilgisi var mı?", "Kapı yanındaki etikette iletişim kanalı yazıyor."),
            ("Dönüşte de aynı hattı mı kullanacağım?", "Karşı yöndeki duraktan aynı hatta binebilirsiniz."),
        ],
    ),
    topic(
        "taksi-yolculugu",
        "Taksi yolculuğu",
        "şehir içi taksi",
        ("yolcu-taksi hizmeti sağlayıcısı",),
        "polite",
        [
            (
                "Tren garına gitmek istiyorum.",
                "Ana yoldan gidersek daha hızlı ulaşırız.",
                "Trafiğin az olduğu güzergâhı seçebilir miyiz?",
                "Elbette, güncel yoğunluğa göre ilerleriz.",
            ),
            (
                "Bagajda yer var mı?",
                "İki küçük valiz rahatça sığar.",
                "Bir çantayı da yanımıza alırız.",
                "Tamam, bagajı buna göre yerleştirelim.",
            ),
            (
                "Yol üzerinde kısa bir durak yapabilir miyiz?",
                "Güzergâhı çok uzatmayacaksa mümkün.",
                "Eczanenin önünde iki dakika beklemeniz yeterli.",
                "Uygun bir yerde güvenli şekilde dururum.",
            ),
            (
                "Klimayı biraz azaltabilir misiniz?",
                "Tabii, sıcaklığı yükseltiyorum.",
                "Camı da azıcık açsak olur mu?",
                "Elbette, arka camı biraz açabilirsiniz.",
            ),
            (
                "Kartla ödeme kabul ediyor musunuz?",
                "Evet, araçta kart cihazı var.",
                "Temassız ödeme de çalışıyor mu?",
                "Evet, yolculuk sonunda kullanabilirsiniz.",
            ),
            (
                "Tahmini varış süresi nedir?",
                "Şu anki trafiğe göre yirmi dakika görünüyor.",
                "Biraz erken ulaşmam gerekiyor.",
                "Kurallara uyarak en akıcı rotayı seçerim.",
            ),
            (
                "Beni ana girişte bırakabilir misiniz?",
                "O girişte kısa süreli durma alanı var.",
                "Kapıya en yakın güvenli yerde ineyim.",
                "Uygun noktada yanaşırım.",
            ),
            (
                "Telefonumu araçta unutmuş olabilirim.",
                "Yolculuğun saatini ve bindiğiniz yeri hatırlıyor musunuz?",
                "Yaklaşık bir saat önce meydandan bindim.",
                "Durak kayıtlarından aracı bulmaya çalışalım.",
            ),
        ],
        [
            ("Müzik sesini biraz kısabilir miyiz?", "Tabii, hemen kısıyorum."),
            ("Fiş alabilir miyim?", "Yolculuk sonunda yazdırabilirim."),
            ("Ön tarafta oturmam uygun mu?", "Elbette, kemerinizi takmanız yeterli."),
            ("Bir arkadaşımı da yoldan alacağız.", "Konumu tarif ederseniz rotaya ekleyelim."),
            ("Yağmur başlayacak gibi görünüyor.", "İnişte kapalı bölüme yanaşmaya çalışırım."),
            ("Ücreti varınca paylaşabilir miyiz?", "Kart ve nakit olarak ikiye bölebiliriz."),
        ],
    ),
    topic(
        "yol-tarifi",
        "Yol tarifi sorma",
        "şehir merkezi",
        ("yol soran-yol tarif eden",),
        "polite",
        [
            (
                "Belediye kütüphanesine nasıl gidebilirim?",
                "Bu caddeden dümdüz ilerleyip ikinci ışıklardan sola dönün.",
                "Yürüyerek uzak mı?",
                "Normal tempoda on dakika kadar sürer.",
            ),
            (
                "En yakın metro girişini arıyorum.",
                "Meydanı geçince sağ tarafta mavi tabelayı göreceksiniz.",
                "Asansörlü giriş de orada mı?",
                "Asansör bir sonraki köşedeki girişte.",
            ),
            (
                "Sahil yoluna buradan çıkılıyor mu?",
                "Alt geçitten karşıya geçip parkın içinden yürüyebilirsiniz.",
                "Bisiklet yolu da aynı yönde mi?",
                "Evet, park çıkışında bisiklet yolu başlıyor.",
            ),
            (
                "Bu sokak müzeye çıkar mı?",
                "Sokak sonunda sağa dönerseniz müzenin arka girişine ulaşırsınız.",
                "Ana giriş hangi tarafta kalıyor?",
                "Binanın çevresinden sola doğru devam edin.",
            ),
            (
                "Otobüs terminaline giden yolu karıştırdım.",
                "Bir kavşak geri dönmeniz gerekiyor.",
                "Orada yön tabelası var mı?",
                "Evet, büyük yeşil tabelada terminal yazıyor.",
            ),
            (
                "Yakındaki eczaneyi tarif edebilir misiniz?",
                "Karşı kaldırımda, fırının iki dükkân yanında.",
                "Geçmek için yaya ışığı nerede?",
                "Kavşağın hemen köşesinde.",
            ),
            (
                "Bu patika parka giriyor mu?",
                "Evet, göletin yanındaki yürüyüş yoluna bağlanıyor.",
                "Aydınlatma var mı?",
                "Ana yol aydınlık, yan patikalar akşam karanlık olabilir.",
            ),
            (
                "Numaralı binayı bulamıyorum.",
                "Tek numaralar yolun diğer tarafında devam ediyor.",
                "Bir sonraki bloktan mı başlamalıyım?",
                "Evet, karşıya geçince numaralar küçülüyor.",
            ),
        ],
        [
            ("Yol üzerinde merdiven var mı?", "Bir kısa merdiven var; yanında rampa da bulunuyor."),
            ("Tabelayı kaçırırsam neye dikkat edeyim?", "Köşedeki saat kulesi iyi bir işaret noktası."),
            ("Dönüş için aynı yolu kullanabilir miyim?", "Evet, en kolay rota yine burası."),
            ("Yağmurda üstü kapalı bir geçiş var mı?", "Çarşının içinden giderseniz çoğu bölüm kapalı."),
            ("Haritada konumu işaretler misiniz?", "Tabii, bulunduğumuz noktayı göstereyim."),
            ("Bu saatte yol kalabalık olur mu?", "İş çıkışına doğru biraz yoğunlaşıyor."),
        ],
    ),
    topic(
        "aile-planlari",
        "Aile planları",
        "aile evi",
        ("aile üyeleri",),
        "informal",
        [
            (
                "Pazar günü hep birlikte ne yapalım?",
                "Hava iyi olursa pikniğe gidebiliriz.",
                "Sabah erken çıkmak gerekir mi?",
                "Kalabalığa kalmamak için dokuz gibi çıkalım.",
            ),
            (
                "Akşam yemeğine kimler geliyor?",
                "Teyzemlerle birlikte toplam altı kişi olacağız.",
                "Masayı büyütmemiz gerekir.",
                "Ben ek parçayı takarım.",
            ),
            (
                "Bu hafta büyükleri ziyaret edelim mi?",
                "Cumartesi öğleden sonra herkes uygun.",
                "Giderken bir tatlı alalım.",
                "Ben önceden arayıp haber veririm.",
            ),
            (
                "Bayram planını netleştirebildik mi?",
                "İlk gün evde, ikinci gün şehir dışında olacağız.",
                "Yol saatini önceden seçelim.",
                "Akşam birlikte seçeneklere bakarız.",
            ),
            (
                "Çocuklarla hangi etkinliğe gidelim?",
                "Bilim merkezindeki atölye uygun görünüyor.",
                "Yaş sınırını kontrol ettin mi?",
                "Evet, ikisi de katılabiliyor.",
            ),
            (
                "Aile fotoğraflarını düzenleyelim mi?",
                "Hafta sonu albümlere ayırabiliriz.",
                "Eski fotoğrafları da tarayalım.",
                "Tarayıcıyı ben hazırlarım.",
            ),
            (
                "Doğum günü için görevleri paylaşalım.",
                "Ben yiyecekleri, sen süslemeyi üstlenebilirsin.",
                "Müzik listesini kim hazırlasın?",
                "Onu da birlikte seçeriz.",
            ),
            (
                "Bu akşam görüntülü konuşma yapalım mı?",
                "Herkes sekizden sonra müsait.",
                "Bağlantıyı aile grubuna gönderelim.",
                "Ben toplantıyı oluşturup paylaşırım.",
            ),
        ],
        [
            ("Planı çok sıkıştırmayalım.", "Arada dinlenmek için zaman bırakırız."),
            ("Herkesin fikrini alalım.", "Gruba iki seçenek yazabiliriz."),
            ("Ulaşımı önceden ayarlayalım.", "Kaç kişi olduğumuz netleşince bakarız."),
            ("Yanımıza atıştırmalık alalım.", "Evden çıkmadan küçük bir çanta hazırlarız."),
            ("Masrafları paylaşmak kolay olur.", "Alışverişten sonra tutarı hesaplarız."),
            ("Dönüş saatini de belirleyelim.", "Ertesi günün programına göre ayarlarız."),
        ],
    ),
    topic(
        "ev-isleri",
        "Ev işleri",
        "paylaşımlı ev",
        ("aynı evi paylaşanlar",),
        "informal",
        [
            (
                "Bu hafta temizlik sırası kimde?",
                "Mutfak bende, salonu sen almıştın.",
                "Banyoyu da birlikte yapalım mı?",
                "Olur, daha çabuk biter.",
            ),
            (
                "Çamaşır makinesi dolmuş.",
                "Renkli çamaşırları akşam çalıştırabiliriz.",
                "Hassas olanları ayırdın mı?",
                "Evet, küçük sepette duruyorlar.",
            ),
            (
                "Salondaki ampul yine söndü.",
                "Yedek ampul çekmecede olmalı.",
                "Merdiveni getirir misin?",
                "Getiririm, elektriği kapatıp değiştiririz.",
            ),
            (
                "Buzdolabını düzenlememiz gerekiyor.",
                "Önce tarihi yaklaşanları öne alalım.",
                "Boş kapları da çıkaralım.",
                "Ben rafları silerken sen ayırabilirsin.",
            ),
            (
                "Çöpleri kim çıkaracak?",
                "Ben çıkarken geri dönüşümü de alırım.",
                "Cam şişeler ayrı torbada.",
                "Tamam, onları konteynere ayrı bırakırım.",
            ),
            (
                "Balkondaki bitkiler susuz kalmış.",
                "Akşam serinliğinde sulayalım.",
                "Büyük saksıya biraz daha su gerekir.",
                "Toprağına bakıp miktarı ayarlarız.",
            ),
            (
                "Dolabın kapağı gevşemiş.",
                "Vidaları sıkmak için küçük tornavida yeterli.",
                "Çekmecede olması lazım.",
                "Bulunca beraber kontrol ederiz.",
            ),
            (
                "Haftalık alışveriş listesini yapalım.",
                "Temel ihtiyaçları ben yazmaya başladım.",
                "Temizlik malzemelerini de ekledin mi?",
                "Eksik olanları şimdi kontrol ederiz.",
            ),
        ],
        [
            ("İşleri bitirince kahve molası verelim.", "Bu iyi bir motivasyon olur."),
            ("Gürültülü işi çok geçe bırakmayalım.", "Akşam olmadan tamamlarız."),
            ("Kullanmadıklarımızı ayıralım.", "Temiz olanları bağış kutusuna koyarız."),
            ("Temizlik ürünlerini karıştırmayalım.", "Her ürünü etiketindeki şekilde kullanırız."),
            ("Pencereleri de kısa süre havalandıralım.", "Temizlik sırasında açık tutabiliriz."),
            ("Görevleri listeye işaretleyelim.", "Böylece neyin kaldığını görürüz."),
        ],
    ),
    topic(
        "komsuluk",
        "Komşuluk",
        "apartman",
        ("komşular",),
        "polite",
        [
            (
                "Akşam kısa süreliğine matkabı kullanmam gerekiyor.",
                "Sekizden önce bitirirseniz sorun olmaz.",
                "En fazla on dakika sürecek.",
                "Önceden haber verdiğiniz için teşekkürler.",
            ),
            (
                "Kargom yanlışlıkla size bırakılmış olabilir mi?",
                "Evet, görevli öğlen bir paket bıraktı.",
                "Müsait olduğunuzda alabilir miyim?",
                "Şimdi evdeyim, uğrayabilirsiniz.",
            ),
            (
                "Apartman toplantısı hangi gün yapılacak?",
                "Yönetim cumartesi akşamını önerdi.",
                "Gündem önceden paylaşılacak mı?",
                "Duyuru panosuna ve gruba eklenecek.",
            ),
            (
                "Üst kattaki su sesi sizden mi geliyor?",
                "Çamaşır makinesi çalışıyor ama sızıntı görmedik.",
                "Tavanımda küçük bir iz oluştu.",
                "Hemen kapatıp birlikte kontrol edelim.",
            ),
            (
                "Yeni taşındım, geri dönüşüm kutuları nerede?",
                "Binanın arkasındaki kapalı bölümde.",
                "Kâğıt ve cam ayrı mı toplanıyor?",
                "Evet, kutuların üzerinde etiketleri var.",
            ),
            (
                "Yarın birkaç saatliğine misafirim gelecek.",
                "Otoparkta ziyaretçi yeri bulunuyor.",
                "Bir araç için kullanabilir miyiz?",
                "Plakayı yönetime bildirmeniz yeterli.",
            ),
            (
                "Kedimi kısa süreliğine kontrol edebilir misiniz?",
                "Öğleden sonra evde olacağım.",
                "Sadece suyuna bakmanız yeterli.",
                "Tabii, anahtarı güvenli şekilde alırım.",
            ),
            (
                "Asansör bakımda mı?",
                "Görevli öğlene kadar süreceğini söyledi.",
                "Bebek arabasıyla çıkmam gerekiyor.",
                "İsterseniz taşımaya yardımcı olabilirim.",
            ),
        ],
        [
            ("Apartman grubuna da bilgi verelim mi?", "Evet, kısa bir not yazmak iyi olur."),
            ("Rahatsızlık olursa bana haber verin.", "Tabii, önce sizinle iletişime geçeriz."),
            ("Yöneticiye birlikte sorabiliriz.", "Akşam girişte görürsek konuşalım."),
            ("Ortak alanı temiz bırakalım.", "İşimiz bitince kontrol ederiz."),
            ("Kapı şifresini yazılı paylaşmayalım.", "Haklısınız, yüz yüze konuşuruz."),
            ("Duyuru panosuna tarih ekleyelim.", "Böylece görmeyen kalmaz."),
        ],
    ),
    topic(
        "okul-ve-ders",
        "Okul ve ders planı",
        "okul ve çalışma alanı",
        ("ders veya çalışma arkadaşları",),
        "polite",
        [
            (
                "Sunum için konuları nasıl paylaşalım?",
                "Giriş bölümünü ben, örnekleri sen hazırlayabilirsin.",
                "Sonuç kısmını birlikte yazalım.",
                "Tamam, akşam taslağı birleştiririz.",
            ),
            (
                "Yarınki dersin sınıfı değişmiş mi?",
                "Duyuruda ikinci kattaki salon yazıyor.",
                "Başlangıç saati aynı mı?",
                "Evet, yalnızca sınıf değişmiş.",
            ),
            (
                "Notların bir bölümünü kaçırdım.",
                "Ders çıkışında fotoğrafını paylaşabilirim.",
                "Özellikle son örnek eksik kaldı.",
                "O kısmı ayrıca işaretlerim.",
            ),
            (
                "Grup ödevinde kaynakları toparladınız mı?",
                "Üç güvenilir kaynak bulduk.",
                "Kaynakçayı aynı biçimde yazalım.",
                "Şablonu dosyanın sonuna ekledim.",
            ),
            (
                "Çalışma salonunda yer bulabilir miyiz?",
                "Öğleden önce genelde boş oluyor.",
                "Sessiz bölümü seçelim.",
                "Pencere yanındaki masalara bakarız.",
            ),
            (
                "Sınav programında iki ders çakışıyor.",
                "Danışmana birlikte bildirebiliriz.",
                "Ekran görüntüsünü de götüreyim.",
                "Evet, tarihleri göstermesi yararlı olur.",
            ),
            (
                "Projeyi teslim etmeden gözden geçirir misin?",
                "Yazım ve akış açısından bakabilirim.",
                "Sayısal sonuçları ben tekrar kontrol ederim.",
                "Son hâlini akşam karşılaştırırız.",
            ),
            (
                "Ders çalışırken kısa aralar verelim mi?",
                "Kırk dakika çalışıp on dakika dinlenebiliriz.",
                "İlk olarak zor konudan başlayalım.",
                "Enerjimiz yüksekken bitirmiş oluruz.",
            ),
        ],
        [
            ("Dosya adlarını düzenli verelim.", "Tarih ve sürüm eklersek karışmaz."),
            ("Toplantı saatini gruba yazalım.", "Herkes onaylayınca kesinleştiririz."),
            ("Kaynakların bağlantılarını da saklayalım.", "Ortak belgeye ayrı bir bölüm açarım."),
            ("Teslimden önce yedek alalım.", "Dosyayı iki farklı yerde tutarız."),
            ("Süreyi aşmamak için prova yapalım.", "Kronometreyle bir kez deneyebiliriz."),
            ("Anlamadığımız yeri derste soralım.", "Soruyu önceden kısa biçimde yazarız."),
        ],
    ),
    topic(
        "is-gunu",
        "İş günü koordinasyonu",
        "ofis",
        ("çalışma arkadaşları",),
        "formal",
        [
            (
                "Bugünkü öncelikleri birlikte netleştirebilir miyiz?",
                "Önce müşteri notlarını, ardından raporu tamamlayalım.",
                "Rapor taslağını öğlene kadar paylaşırım.",
                "Ben de geri bildirimi gün sonunda iletirim.",
            ),
            (
                "Toplantıyı yarım saat ertelememiz mümkün mü?",
                "Takvimde bir sonraki aralık uygun görünüyor.",
                "Katılımcılara güncelleme gönderelim.",
                "Davet saatini şimdi değiştiriyorum.",
            ),
            (
                "Bu görevin sorumlusu kim olacak?",
                "İlk hazırlığı siz, son kontrolü ben üstlenebilirim.",
                "Teslim ölçütlerini belgeye ekleyelim.",
                "Evet, beklentiler herkes için net olur.",
            ),
            (
                "Haftalık raporda hangi verileri kullanalım?",
                "Onaylanmış son tabloyu temel alalım.",
                "Önceki haftayla karşılaştırma ekleyeyim mi?",
                "Evet, değişimi görmeyi kolaylaştırır.",
            ),
            (
                "Müşteri görüşmesinin notlarını paylaşabilir misiniz?",
                "Kararları ve açık maddeleri özetledim.",
                "Sorumluların tarihlerini de ekleyelim.",
                "Güncel sürümde hepsi yer alacak.",
            ),
            (
                "Bugün ofisten biraz erken ayrılmam gerekiyor.",
                "Acil işlerin devrini yaparsanız uygundur.",
                "Devam eden görevi ekip arkadaşımıza aktaracağım.",
                "Takvime kısa bir not düşmeniz yeterli.",
            ),
            (
                "Dosyanın son sürümünü bulamıyorum.",
                "Ortak klasörde tarihli sürüm bulunuyor.",
                "Üzerinde çalışmadan önce kilitleyeyim mi?",
                "Evet, eş zamanlı değişiklikleri önler.",
            ),
            (
                "Bu talebin kapsamı genişlemiş görünüyor.",
                "Yeni maddeleri ayrı bir aşamaya alabiliriz.",
                "Öncelikli olanları bugün tamamlayalım.",
                "Kalanlar için yeni tarih planlarız.",
            ),
        ],
        [
            ("Kararı kısa bir notla kayıt altına alalım.", "Toplantı özetine ekliyorum."),
            ("Bağımlı olduğumuz ekibe haber verelim.", "İlgili kişileri güncellemeye eklerim."),
            ("Teslimden önce ikinci bir kontrol yapalım.", "Kontrol listesini birlikte tamamlarız."),
            ("Dosyada kişisel bilgi kullanmayalım.", "Yalnızca gerekli iş verilerini bırakırız."),
            ("Gecikme riski oluşursa erken bildirelim.", "Takvim değişikliğini beklemeden paylaşırız."),
            ("Bir sonraki adımı da belirleyelim.", "Sorumlu ve tarihi özetin sonuna eklerim."),
        ],
    ),
    topic(
        "uzaktan-calisma",
        "Uzaktan çalışma",
        "evden çalışma ortamı",
        ("uzaktan çalışan ekip arkadaşları",),
        "formal",
        [
            (
                "Görüntülü toplantıda sesim kesiliyor mu?",
                "Şu an net geliyor, yalnızca başta kısa bir kesinti oldu.",
                "Kamerayı kapatırsam bağlantı rahatlayabilir.",
                "Gerekirse sunumu ekran paylaşımıyla sürdürürüz.",
            ),
            (
                "Ortak belgeye erişebiliyor musunuz?",
                "Bağlantı açılıyor fakat düzenleme iznim yok.",
                "İzin seviyesini şimdi güncelliyorum.",
                "Tamam, yeniden açınca kontrol ederim.",
            ),
            (
                "Bugünkü odak saatimi takvime ekledim.",
                "Acil olmayan konuları sonrasına bırakırım.",
                "Öğleden sonra mesajları topluca yanıtlayacağım.",
                "Ekip kanalına da kısa bilgi geçelim.",
            ),
            (
                "Dosya yüklemesi oldukça yavaş ilerliyor.",
                "Boyutu küçültüp yeniden deneyebiliriz.",
                "Orijinalini arşivde tutacağım.",
                "Paylaşım için sıkıştırılmış sürüm yeterli.",
            ),
            (
                "Toplantı kaydına gerçekten ihtiyaç var mı?",
                "Katılamayan iki kişi için yararlı olabilir.",
                "Başlamadan önce herkesten onay alalım.",
                "Onay olmazsa yalnızca yazılı özet paylaşırız.",
            ),
            (
                "Saat farkı nedeniyle toplantıya katılamayacağım.",
                "Sorularınızı önceden belgeye ekleyebilirsiniz.",
                "Kararları daha sonra özetten takip ederim.",
                "Gerekirse kısa bir tekrar görüşmesi ayarlarız.",
            ),
            (
                "Evdeki çalışma ortamı bugün biraz gürültülü.",
                "Mikrofonu konuşmadığınız sırada kapatabilirsiniz.",
                "Sunum bölümüm gelince sessiz bir odaya geçerim.",
                "Akışta size önceden haber veririm.",
            ),
            (
                "Görev panosundaki durum güncel değil.",
                "Tamamlanan işleri birlikte işaretleyelim.",
                "Ben kendi kartlarıma kısa not eklerim.",
                "Ben de bağımlılıkları kontrol ederim.",
            ),
        ],
        [
            (
                "Bağlantı koparsa telefonla devam edebiliriz.",
                "Alternatif numarayı toplantı notuna eklemeyelim; kanaldan ulaşırız.",
            ),
            ("Ekran paylaşımında özel sekmeleri kapatayım.", "Yalnızca ilgili pencereyi seçmeniz daha güvenli."),
            ("Kısa bir ara vermek iyi olur.", "On dakika sonra aynı bağlantıda buluşalım."),
            ("Notları toplantı sonunda paylaşalım.", "Kararları önce katılımcılarla doğrularız."),
            ("Saatleri yerel zamanla da yazalım.", "Davet her katılımcıya kendi saatinde görünür."),
            ("Bildirimleri sunum sırasında kapatacağım.", "Dikkatin dağılmasını önler."),
        ],
    ),
    topic(
        "saglik-randevusu",
        "Sağlık randevusu planlama",
        "sağlık merkezi danışması",
        ("hasta-sağlık kuruluşu görevlisi",),
        "polite",
        [
            (
                "Genel kontrol için randevu almak istiyorum.",
                "Hafta içi sabah ve öğleden sonra boşluklarımız var.",
                "Perşembe sabahı benim için daha uygun.",
                "Saat ona bir randevu ayırabilirim.",
            ),
            (
                "Randevu saatimi değiştirmem gerekiyor.",
                "Aynı gün içinde daha geç bir saat uygun.",
                "Öğleden sonraya alabilir miyiz?",
                "Saat üç için güncelledim.",
            ),
            (
                "Muayeneye gelirken hangi belgeler gerekli?",
                "Kimlik ve varsa önceki tetkik sonuçları yeterli.",
                "Belgeleri dijital olarak gösterebilir miyim?",
                "Kabul koşulunu merkezden gelirken teyit edebilirsiniz.",
            ),
            (
                "Kontrol randevusunun süresi ne kadar?",
                "Genellikle yirmi ila otuz dakika planlanıyor.",
                "Biraz erken gelmem gerekir mi?",
                "Kayıt için on dakika önce gelmeniz iyi olur.",
            ),
            (
                "Bugünkü randevuma yetişemeyeceğim.",
                "İsterseniz başka bir güne taşıyabiliriz.",
                "En yakın uygun günü kontrol eder misiniz?",
                "Yarın öğleden sonra bir boşluk var.",
            ),
            (
                "Sonuçların hazır olup olmadığını nasıl öğrenebilirim?",
                "Hasta portalındaki bildirim bölümünden takip edebilirsiniz.",
                "Bildirim gelmezse merkezi arayayım mı?",
                "Evet, kayıt birimi durumunu kontrol edebilir.",
            ),
            (
                "Randevu hangi binadaydı?",
                "Ana binanın ikinci katındaki poliklinikte.",
                "Asansör girişe yakın mı?",
                "Danışmanın sağındaki koridorda.",
            ),
            (
                "Yanımda bir refakatçi gelebilir mi?",
                "Bekleme alanı uygunsa bir kişi gelebilir.",
                "Bunu randevu notuna ekleyebilir misiniz?",
                "Elbette, talebinizi not ettim.",
            ),
        ],
        [
            ("Tıbbi konuyu görevli yerine hekimle görüşeceğim.", "En doğrusu değerlendirmeyi randevuda yapmanızdır."),
            ("İptal koşulunu öğrenebilir miyim?", "Mümkün olduğunca önceden haber vermeniz yeterli."),
            ("Girişte sıra numarası almam gerekir mi?", "Randevulu kayıt bölümünden işlem yapılıyor."),
            ("Ulaşım için toplu taşıma bilgisi var mı?", "Merkezin sitesinde güncel yol tarifi bulunuyor."),
            ("Bekleme alanı hangi katta?", "Poliklinik girişinin hemen karşısında."),
            ("Randevu teyidi mesajla gelecek mi?", "Sistem bir gün önce hatırlatma gönderiyor."),
        ],
    ),
    topic(
        "spor-aktivitesi",
        "Spor aktivitesi planlama",
        "park ve spor merkezi",
        ("birlikte spor yapan kişiler",),
        "informal",
        [
            (
                "Akşam koşuya çıkalım mı?",
                "Hava serinleyince parkta koşabiliriz.",
                "Bu kez kısa parkuru seçelim.",
                "Tamam, tempoyu da rahat tutarız.",
            ),
            (
                "Yüzme saatini değiştirelim mi?",
                "Sabah havuz daha sakin oluyor.",
                "Cumartesi dokuz bana uygun.",
                "Girişte buluşuruz.",
            ),
            (
                "Top biraz inmiş görünüyor.",
                "Pompayı yanımıza alalım.",
                "Sahaya varmadan kontrol ederiz.",
                "Gerekirse orada biraz şişiririz.",
            ),
            (
                "Bugün esneme çalışmasına ağırlık verelim.",
                "Dünkü antrenmandan sonra iyi olur.",
                "Hareketleri acele etmeden yapalım.",
                "Ağrı olursa zorlamadan bırakırız.",
            ),
            (
                "Bisiklet turu için hangi rotayı seçelim?",
                "Nehir kenarındaki yol daha düz.",
                "Trafikten uzak olsun yeter.",
                "Bisiklet yolundan ayrılmayız.",
            ),
            (
                "Maç için bir kişi eksik kaldı.",
                "Gruba yeniden yazabiliriz.",
                "Başlangıcı yarım saat erteleyelim mi?",
                "Önce herkesin uygunluğunu soralım.",
            ),
            (
                "Spor salonu bugün açık mı?",
                "Uygulamada normal saatte kapanacağı yazıyor.",
                "Yoğunluk durumuna da bakalım.",
                "Şu an orta seviyede görünüyor.",
            ),
            (
                "Yağmur başlarsa planı ne yapacağız?",
                "Kapalı salonda masa tenisi oynayabiliriz.",
                "Önceden masa ayırmak gerekir mi?",
                "Telefonla sorup netleştirelim.",
            ),
        ],
        [
            ("Yanımıza su almayı unutmayalım.", "Çıkmadan şişeleri doldururuz."),
            ("Isınmadan başlamayalım.", "İlk on dakikayı ısınmaya ayırırız."),
            ("Dönüşte kısa bir mola veririz.", "Parktaki banklarda dinlenebiliriz."),
            ("Ekipmanı paylaşarak kullanırız.", "Sırayı baştan belirleyelim."),
            ("Bugünkü hedefi abartmayalım.", "Kendimizi iyi hissettiğimiz yerde bırakırız."),
            ("Saati gruba yazalım.", "Herkes görsün diye sabitleyebilirim."),
        ],
    ),
    topic(
        "hobi-kursu",
        "Hobi ve kurs",
        "atölye ve kurs merkezi",
        ("kursiyer-kurs hakkında bilgi veren kişi",),
        "polite",
        [
            (
                "Seramik atölyesine ilk kez katılacağım.",
                "Başlangıç grubu temel tekniklerle ilerliyor.",
                "Malzemeleri yanımda getirmem gerekiyor mu?",
                "İlk ders için tüm malzemeler atölyede var.",
            ),
            (
                "Fotoğraf yürüyüşü hangi gün yapılacak?",
                "Pazar sabahı eski şehirde buluşulacak.",
                "Tripod taşımak gerekli mi?",
                "Zorunlu değil, hafif ekipman yeterli.",
            ),
            (
                "Gitar dersinin saatini değiştirebilir miyiz?",
                "Cuma akşamı başka bir boşluk bulunuyor.",
                "Bir saat geç olması uygun.",
                "Dersi o saate taşıyabilirim.",
            ),
            (
                "Resim kursunda hangi boyayı kullanacağız?",
                "Bu ay sulu boya tekniklerine geçiyoruz.",
                "Orta boy bir fırça yeterli olur mu?",
                "İki farklı kalınlık getirmeniz daha rahat olur.",
            ),
            (
                "Dans dersine eş olmadan katılabilir miyim?",
                "Evet, derste eşleşmeler dönüşümlü yapılıyor.",
                "Başlangıç seviyesinde olduğumu belirteyim.",
                "Eğitmen ilk bölümde adımları yavaş anlatıyor.",
            ),
            (
                "Kitap kulübünün yeni seçimi belli oldu mu?",
                "Grup kısa bir öykü kitabında karar kıldı.",
                "Toplantıya kadar tamamlamak gerekir mi?",
                "İlk yarıyı okumak tartışma için yeterli.",
            ),
            (
                "Dikiş atölyesinde makine sağlanıyor mu?",
                "Katılımcılar için ortak makineler bulunuyor.",
                "Kendi makasımı getirebilir miyim?",
                "Elbette, etiketlemeniz yeterli.",
            ),
            (
                "Kurs kaydımı bir sonraki aya ertelemek istiyorum.",
                "Yeni dönem kontenjanını kontrol edebilirim.",
                "Hafta içi grubu benim için daha uygun.",
                "Salı grubunda boş yer bulunuyor.",
            ),
        ],
        [
            ("Ders notları sonradan paylaşılacak mı?", "Özet dosyası katılımcılara gönderilecek."),
            ("Bir arkadaşım deneme dersine gelebilir mi?", "Önceden kayıt yaptırırsa katılabilir."),
            ("Atölye önlüğü gerekli mi?", "Kirlenebilecek rahat bir kıyafet yeterli."),
            ("Çalışmaları eve götürebilir miyiz?", "Kuruması gerekenler dışında ders sonunda alabilirsiniz."),
            ("Ara verdiğimizde malzemeleri nerede bırakacağız?", "İsimli raflarda güvenle kalabilir."),
            ("Geri bildirim için ayrıca zaman ayrılıyor mu?", "Dersin sonunda kısa değerlendirme yapılıyor."),
        ],
    ),
    topic(
        "hava-ve-plan",
        "Hava durumuna göre plan",
        "şehir içi günlük yaşam",
        ("birlikte günlük plan yapan kişiler",),
        "informal",
        [
            (
                "Öğleden sonra yağmur bekleniyormuş.",
                "Pikniği sabah yaparsak yakalanmayız.",
                "Yedek olarak kapalı bir yer de seçelim.",
                "Yakındaki müzeyi plana ekleyebiliriz.",
            ),
            (
                "Bugün hava çok sıcak olacak.",
                "Yürüyüşü güneş batmaya yakın yapalım.",
                "Yanımıza yeterince su alalım.",
                "Gölgeli parkuru seçeriz.",
            ),
            (
                "Rüzgâr bisiklet için fazla güçlü mü?",
                "Kıyı yolu açık alanda kalıyor.",
                "Orman içindeki rotaya geçelim mi?",
                "Daha korunaklı olduğu için iyi olur.",
            ),
            (
                "Sabah sis varmış, yola çıkalım mı?",
                "Görüş açılana kadar biraz bekleyebiliriz.",
                "Programı bir saat kaydıralım.",
                "Herkese yeni saati haber veririm.",
            ),
            (
                "Akşam serinleyecekmiş.",
                "İnce bir ceket almak iyi olur.",
                "Dışarıda uzun kalmayacağız zaten.",
                "Yine de hazırlıklı oluruz.",
            ),
            (
                "Kar yağarsa toplu taşıma aksayabilir.",
                "Evden çalışma seçeneğini kullanalım.",
                "Sabah durumu tekrar kontrol ederiz.",
                "Gerekirse toplantıları çevrim içi yaparız.",
            ),
            (
                "Hava açtı, planı dışarı alalım mı?",
                "Bahçedeki masalar uygun olabilir.",
                "Önce yer ayırtalım.",
                "Ben arayıp müsaitliği sorarım.",
            ),
            (
                "Yağmur yeni dindi ama yollar ıslak.",
                "Koşu yerine kısa bir yürüyüş yapabiliriz.",
                "Kaygan olmayan ana yolu seçelim.",
                "Parkın taş döşeli kısmında kalırız.",
            ),
        ],
        [
            ("Hava tahminini çıkmadan bir kez daha kontrol ederiz.", "Son saate yakın bilgi daha güvenilir olur."),
            ("Şemsiyeyi çantaya atalım.", "Yer kaplamayan küçük olanı alırım."),
            ("Plan değişirse gruba yazalım.", "Herkes görsün diye hemen bildiririz."),
            ("Açık alanda uzun beklemeyelim.", "Buluşma saatini net tutarız."),
            ("Güneşli olsa da gölgede oturalım.", "Öğle saatinde daha rahat olur."),
            ("Dönüş yolunu da hava durumuna göre seçeriz.", "Toplu taşıma seçeneğini açık tutalım."),
        ],
    ),
    topic(
        "seyahat-plani",
        "Seyahat planlama",
        "ev ve seyahat hazırlığı",
        ("birlikte seyahat planlayan kişiler",),
        "informal",
        [
            (
                "Hafta sonu için hangi şehre gidelim?",
                "Trenle kolay ulaşabileceğimiz bir yer seçelim.",
                "Yol üç saatten uzun olmasın.",
                "Yakındaki seçenekleri karşılaştırırım.",
            ),
            (
                "Biletleri şimdi alalım mı?",
                "Saatler kesinleştiyse beklemeyelim.",
                "Sabah seferi daha uygun görünüyor.",
                "Dönüşü de aynı anda seçelim.",
            ),
            (
                "Valizi çok doldurmak istemiyorum.",
                "İki günlük kıyafet ve yağmurluk yeter.",
                "Rahat ayakkabıyı mutlaka alacağım.",
                "Diğerlerini ortak kullanabiliriz.",
            ),
            (
                "Gezilecek yerleri sıraya koydun mu?",
                "Birbirine yakın olanları aynı güne topladım.",
                "Arada boş zaman da bırakalım.",
                "Programı saat saat doldurmayız.",
            ),
            (
                "Konaklama merkeze uzak mı?",
                "Toplu taşımayla on beş dakika görünüyor.",
                "Gece dönüşü kolay olur mu?",
                "Son sefer saatini ayrıca kontrol edelim.",
            ),
            (
                "Yola çıkmadan evde neyi kontrol edelim?",
                "Pencereler, prizler ve suyu sırayla kontrol ederiz.",
                "Anahtarı komşuya bırakmayacağız değil mi?",
                "Gerek olmadığı için yanımızda tutarız.",
            ),
            (
                "Yemek için önceden rezervasyon gerekir mi?",
                "Popüler iki yer için gerekebilir.",
                "Bir akşamı plansız bırakalım.",
                "Yerel bir yer bulmak daha keyifli olur.",
            ),
            (
                "Dönüş gününü uzatma ihtimalimiz var mı?",
                "İş programımız izin verirse bir gün ekleyebiliriz.",
                "Değişebilir bilet seçelim.",
                "Farkı çok değilse esnek olanı alırız.",
            ),
        ],
        [
            ("Belgelerin çevrim dışı kopyasını saklayalım.", "Telefonlarda güvenli bir klasöre indiririz."),
            ("Haritayı da çevrim dışı indirelim.", "İnternet çekmezse işimize yarar."),
            ("Bütçeyi günlük olarak takip edelim.", "Ortak harcamaları kısa bir listeye yazarız."),
            ("Çok erken kalkacağımız güne ağır plan koymayalım.", "İlk günü daha sakin tutarız."),
            ("Yerel ulaşım kartını araştırırım.", "Bilet seçenekleriyle birlikte karşılaştırırız."),
            ("Bir yakınımıza genel planı bırakalım.", "Yalnızca gerekli seyahat bilgisini paylaşırız."),
        ],
    ),
    topic(
        "otel-konaklama",
        "Otel konaklaması",
        "otel resepsiyonu",
        ("misafir-otel çalışanı",),
        "polite",
        [
            (
                "Rezervasyonumu kontrol edebilir misiniz?",
                "Tarih ve oda türü bilgisi sistemde görünüyor.",
                "Sessiz oda tercihimi de eklemiştim.",
                "Evet, üst kattaki odalardan biri ayrılmış.",
            ),
            (
                "Giriş saatinden biraz önce geldim.",
                "Odanız hazırsa erken giriş sağlayabiliriz.",
                "Hazır değilse valizi bırakabilir miyim?",
                "Elbette, emanet bölümünde saklarız.",
            ),
            (
                "Odadaki klima çalışmıyor gibi görünüyor.",
                "Teknik ekibi yönlendirebilirim.",
                "Bu sırada başka bir oda mümkün mü?",
                "Kontrolden sonra çözülmezse oda değişikliği yaparız.",
            ),
            (
                "Kahvaltı hangi katta servis ediliyor?",
                "Giriş katındaki restoranda.",
                "Saat kaça kadar devam ediyor?",
                "Hafta içi ona kadar açık.",
            ),
            (
                "Çıkış saatini bir saat uzatabilir miyim?",
                "Odanın sonraki rezervasyonunu kontrol etmem gerekiyor.",
                "Mümkün değilse normal saatte çıkarım.",
                "Şu an için bir saat uzatma uygun görünüyor.",
            ),
            (
                "Odaya ek havlu rica edebilir miyim?",
                "Kat görevlisine hemen haber verebilirim.",
                "İki adet yeterli olacak.",
                "Birazdan odanıza bırakılacak.",
            ),
            (
                "Yakındaki ulaşım seçeneklerini öğrenebilir miyim?",
                "Otobüs durağı köşede, metro ise on dakika yürüme mesafesinde.",
                "Havalimanı için hangisi daha kolay?",
                "Yoğunluğa göre metro daha öngörülebilir.",
            ),
            (
                "Faturayı konaklama sonunda alabilir miyim?",
                "Evet, çıkışta hazırlayabiliriz.",
                "Kalemleri ayrı göstermeniz mümkün mü?",
                "Oda ve ek hizmetler ayrı satırda yer alır.",
            ),
        ],
        [
            ("Kablosuz ağ bilgisi odada bulunuyor mu?", "Giriş kartının kılıfında kullanım bilgisi var."),
            ("Rahatsız edilmemek için kapıya işaret asacağım.", "Kat ekibi işareti gördüğünde odaya girmez."),
            ("Merdiveni kullanmak istersem hangi tarafta?", "Asansörlerin arkasındaki koridorda."),
            (
                "Emanet kasasının kullanımını anlatabilir misiniz?",
                "Odadaki yönergeyi izleyebilir veya yardım isteyebilirsiniz.",
            ),
            ("Gece giriş kapısı açık kalıyor mu?", "Resepsiyon gün boyunca hizmet veriyor."),
            ("Çıkışta taksi çağırabilir misiniz?", "İstediğiniz saat için yardımcı olabiliriz."),
        ],
    ),
    topic(
        "giyim-alisverisi",
        "Giyim alışverişi",
        "giyim mağazası",
        ("müşteri-mağaza çalışanı",),
        "polite",
        [
            (
                "Bu gömleğin bir büyük bedeni var mı?",
                "Depoda aynı rengin büyük bedeni bulunuyor.",
                "Denemek için getirebilir misiniz?",
                "Elbette, kabine bırakırım.",
            ),
            (
                "Günlük kullanıma uygun rahat bir ayakkabı arıyorum.",
                "Yumuşak tabanlı modeller bu rafta.",
                "Koyu renk bir seçenek var mı?",
                "Aynı modelin laciverti de bulunuyor.",
            ),
            (
                "Bu ceketin kumaşı yağmura dayanıklı mı?",
                "Hafif yağmur için su itici kaplaması var.",
                "Bakım talimatı etiketinde yazıyor mu?",
                "Evet, iç cebin yanındaki etikette.",
            ),
            (
                "Hediye için beden konusunda kararsızım.",
                "Değişim kartıyla birlikte alabilirsiniz.",
                "Etikette fiyat görünmesin lütfen.",
                "Fiyat kısmını kapatıp hediye paketi yaparız.",
            ),
            (
                "Paça boyunu kısaltma hizmetiniz var mı?",
                "Evet, ölçü alındıktan sonra birkaç gün sürüyor.",
                "Teslim tarihini önceden öğrenebilir miyim?",
                "Terzi yoğunluğunu kontrol edip netleştiririz.",
            ),
            (
                "Bu ürün indirim kapsamında mı?",
                "Etiketli ürünlere kasada ek indirim uygulanıyor.",
                "İade koşulu değişiyor mu?",
                "İndirimli ürünlerde de fişle iade kabul ediliyor.",
            ),
            (
                "Deneme kabininde unuttuğum bir atkı vardı.",
                "Rengini tarif edebilir misiniz?",
                "Açık gri ve ince dokuluydu.",
                "Bulunan eşyalar bölümünü kontrol ediyorum.",
            ),
            (
                "İnternetten aldığım ürünü mağazada değiştirebilir miyim?",
                "Sipariş kaydıyla birlikte değişim yapılabiliyor.",
                "Farklı bir renkle değiştirmek istiyorum.",
                "Stok varsa aynı ürünle değiştiririz.",
            ),
        ],
        [
            ("Ürünü doğal ışıkta görebilir miyim?", "Girişe yakın aynada rengi daha doğru görünür."),
            ("Kumaşın içeriğine birlikte bakalım.", "Etikette oranlar açıkça yazıyor."),
            ("Çantaya koymak yerine askıda taşıyabilir miyim?", "Koruyucu kılıfla teslim edebiliriz."),
            ("Fişi dijital olarak alabilir miyim?", "E-posta vermeden uygulama koduyla kaydedebilirsiniz."),
            ("Başka şubede stok var mı?", "Sistemden yakın şubeleri kontrol edebilirim."),
            ("Karar vermeden bir tur daha bakacağım.", "Elbette, ürünü kısa süre kasada ayırabiliriz."),
        ],
    ),
    topic(
        "teknoloji-destegi",
        "Günlük teknoloji desteği",
        "ev ve teknik destek masası",
        ("destek isteyen-destek veren",),
        "polite",
        [
            (
                "Kablosuz ağa bağlanıyorum ama internet açılmıyor.",
                "Önce diğer cihazlarda bağlantıyı kontrol edelim.",
                "Telefonda da aynı sorun var.",
                "Modemin bağlantı ışıklarına bakabiliriz.",
            ),
            (
                "Telefonumda depolama alanı azaldı.",
                "Büyük dosyaları ve kullanılmayan uygulamaları inceleyelim.",
                "Fotoğrafları silmeden yer açmak istiyorum.",
                "Yedek durumunu doğrulayıp kopyaları düzenleyebiliriz.",
            ),
            (
                "Yazıcı belgeyi sırada bekletiyor.",
                "Yazıcı durumunda çevrim dışı uyarısı var mı?",
                "Ekranda bağlantı bekleniyor yazıyor.",
                "Aynı ağa bağlı olduğundan emin olup yeniden deneyelim.",
            ),
            (
                "Görüntülü aramada mikrofon çalışmıyor.",
                "Uygulamanın mikrofon iznini kontrol edelim.",
                "İzin kapalı görünüyor.",
                "Açtıktan sonra test görüşmesi yapabiliriz.",
            ),
            (
                "Dosyayı yanlışlıkla farklı klasöre kaydettim.",
                "Son kullanılanlar listesinden bulabiliriz.",
                "Dosya adının bir kısmını hatırlıyorum.",
                "Aramada o ifadeyi kullanarak yerini bulalım.",
            ),
            (
                "Ekrandaki yazılar çok küçük görünüyor.",
                "Görüntü ölçeğini artırabiliriz.",
                "Sadece tarayıcıda büyütmek yeterli.",
                "Tarayıcının yakınlaştırma ayarını kullanalım.",
            ),
            (
                "Yeni güncellemeden sonra uygulama yavaş açılıyor.",
                "Önce yeniden başlatıp bekleyen işlemleri tamamlayalım.",
                "Verilerim etkilenir mi?",
                "Normal yeniden başlatma dosyaları silmez; yine de açık işleri kaydedin.",
            ),
            (
                "Bilinmeyen bir bağlantı içeren mesaj aldım.",
                "Bağlantıyı açmadan göndereni başka kanaldan doğrulayın.",
                "Mesajı silmem yeterli mi?",
                "Şüpheli olarak bildirmek de diğer kullanıcıları koruyabilir.",
            ),
        ],
        [
            ("Parolayı konuşmada paylaşmayacağım.", "Doğru; destek için parola gerekmez."),
            ("Değişiklikten önce yedek alalım.", "Geri dönüş gerektiğinde işimizi kolaylaştırır."),
            ("Adımları tek tek not edebilir miyiz?", "Evet, hangi adımın işe yaradığını görürüz."),
            ("Sorun tekrar olursa ekran görüntüsü alırım.", "Kişisel bilgileri kapatarak paylaşmanız iyi olur."),
            ("Aynı anda çok ayar değiştirmeyelim.", "Her değişiklikten sonra sonucu test ederiz."),
            (
                "Cihazı yetkili servise götürmek gerekirse verileri kaldırırım.",
                "Önce yedekleyip hesaplardan çıkış yapmak güvenli olur.",
            ),
        ],
    ),
    topic(
        "fatura-ve-odeme",
        "Fatura ve ödeme takibi",
        "ev ve hizmet merkezi",
        ("aynı hanede ödeme takibi yapan kişiler",),
        "polite",
        [
            (
                "Bu ayki elektrik faturası beklediğimden yüksek gelmiş.",
                "Önce tüketim dönemini önceki ayla karşılaştıralım.",
                "Sayaç okuma tarihleri farklı görünüyor.",
                "Gün sayısı farkı tutarı etkilemiş olabilir.",
            ),
            (
                "Otomatik ödeme talimatı aktif mi?",
                "Hesap ekranında bir sonraki fatura için etkin görünüyor.",
                "Son ödeme gününden önce çekilecek mi?",
                "Sistem genellikle son günden bir gün önce dener.",
            ),
            (
                "İnternet faturasında ek bir kalem var.",
                "Hizmet detayındaki açıklamayı kontrol edebiliriz.",
                "Tek seferlik kurulum ücreti yazıyor.",
                "Sözleşmedeki taksit planıyla karşılaştıralım.",
            ),
            (
                "Ev giderlerini bu ay nasıl paylaşalım?",
                "Ortak giderleri kişi sayısına göre bölebiliriz.",
                "Kişisel harcamaları ayrı bırakalım.",
                "Tabloya yalnızca ortak kalemleri ekleriz.",
            ),
            (
                "Ödemeyi yaptım ama sistemde görünmüyor.",
                "İşlem bazen aynı gün içinde güncelleniyor.",
                "Dekontu şimdilik saklayayım.",
                "Evet, durum değişmezse destek birimine sunabilirsiniz.",
            ),
            (
                "Faturanın dijital kopyasını bulamıyorum.",
                "Hizmet sağlayıcının belge bölümünde olabilir.",
                "Dönem filtresini yanlış seçmişim.",
                "Doğru ayı seçince belge görünür.",
            ),
            (
                "Abonelik fiyatı gelecek ay değişecekmiş.",
                "Yeni tutarı ve iptal koşulunu birlikte inceleyelim.",
                "Kullanmıyorsak yenilenmeden kapatalım.",
                "Önce ihtiyaç durumunu netleştiririz.",
            ),
            (
                "Son ödeme tarihini kaçırmak istemiyorum.",
                "Takvime birkaç gün önceden hatırlatma ekleyebiliriz.",
                "Bildirim yalnızca cihazımda kalsın.",
                "Özel ayrıntı yazmadan genel bir hatırlatma koyarız.",
            ),
        ],
        [
            ("Hesap bilgilerini mesajda paylaşmayalım.", "Yalnızca resmî uygulama üzerinden işlem yaparız."),
            ("Ödeme sonrası belgenin kopyasını saklayalım.", "Tarih klasöründe arşivleyebiliriz."),
            ("Tutarı tekrar hesaplayalım.", "Kalemleri tek tek toplamak hatayı gösterir."),
            ("Destekle görüşürken işlem tarihini söyleyelim.", "Gizli bilgi vermeden süreci tarif ederiz."),
            ("Ortak tabloyu ay sonunda kapatalım.", "Eksik girişleri tamamlayınca kilitleriz."),
            ("Yeni ücret için alternatifleri karşılaştıralım.", "Koşulları aynı kullanım üzerinden değerlendirelim."),
        ],
    ),
    topic(
        "kargo-teslimati",
        "Kargo ve teslimat",
        "ev ve teslimat noktası",
        ("alıcı-kargo hizmeti sağlayıcısı",),
        "polite",
        [
            (
                "Teslimat bugün hangi saat aralığında gelir?",
                "Dağıtım planında öğleden sonra görünüyor.",
                "Gelmeden kısa süre önce haber verilebilir mi?",
                "Sürücü uygun olduğunda bildirim gönderecek.",
            ),
            (
                "Paketi teslimat noktasından almak istiyorum.",
                "Yönlendirmeyi dağıtıma çıkmadan yapabiliriz.",
                "Yarın akşam alabilirim.",
                "Paket iki gün boyunca noktada bekletilir.",
            ),
            (
                "Kutunun köşesi ezilmiş görünüyor.",
                "Teslim almadan önce durumu kayda geçirebiliriz.",
                "İçeriği görevlinin yanında kontrol edeyim.",
                "Evet, hasar varsa tutanağa ekleriz.",
            ),
            (
                "Adres açıklamasını güncellemem gerekiyor.",
                "Gizli adres ayrıntısını burada paylaşmadan resmî takip ekranını kullanın.",
                "Uygulamadan bina tarifini ekleyebilirim.",
                "Dağıtım ekibi güncel notu oradan görür.",
            ),
            (
                "Evde olmayacağım; komşuma bırakılabilir mi?",
                "Alıcı onayı sistemden verildiğinde mümkün.",
                "Önceden kendisine de haber vereceğim.",
                "Teslimde kimlik doğrulama kuralı uygulanır.",
            ),
            (
                "Gönderi hareketlerinde iki gündür değişiklik yok.",
                "Aktarma merkezindeki yoğunluk nedeniyle gecikmiş olabilir.",
                "Tahmini tarih güncellenir mi?",
                "Yeni tarama yapıldığında takip ekranına yansır.",
            ),
            (
                "Yanlış ürün teslim edildi.",
                "Paket etiketini sipariş bilgisiyle karşılaştıralım.",
                "Kutu benim adıma ama içerik farklı.",
                "Satıcıyla iade sürecini başlatmanız gerekir.",
            ),
            (
                "İade paketini nasıl hazırlamalıyım?",
                "Ürünü koruyacak şekilde kapatıp iade etiketini ekleyin.",
                "Eski etiket görünür kalmasın mı?",
                "Karışmaması için eski barkodu kapatın.",
            ),
        ],
        [
            ("Takip kodunu herkese açık paylaşmayacağım.", "Yalnızca resmî kanalda kullanmanız iyi olur."),
            ("Teslim belgesinin kopyasını saklayalım.", "İade sonuçlanana kadar gerekli olabilir."),
            ("Paket ağırsa girişte yardım isteyebilirim.", "Teslim görevlisine önceden not düşebilirsiniz."),
            ("Zili duymama ihtimalim var.", "Telefon bildirimini açık tutmanız yardımcı olur."),
            ("Dış ambalajı hemen atmayacağım.", "İçeriği kontrol edene kadar saklamak iyi olur."),
            ("Teslim saatini takvime ekleyeyim.", "Belirlenen aralığı kaçırmamış olursunuz."),
        ],
    ),
    topic(
        "kutlama-organizasyonu",
        "Kutlama organizasyonu",
        "ev ve etkinlik mekânı",
        ("birlikte kutlama planlayan kişiler",),
        "informal",
        [
            (
                "Doğum günü için kaç kişilik hazırlık yapalım?",
                "Şimdilik on kişi geleceğini söyledi.",
                "İki kişilik pay fazladan olsun.",
                "Yiyecekleri on iki kişiye göre ayarlarız.",
            ),
            (
                "Süslemelerde sade bir tema seçelim.",
                "İki renk kullanırsak düzenli görünür.",
                "Masa için küçük çiçekler yeter.",
                "Duvara da tek bir yazı asarız.",
            ),
            (
                "Müzik listesini hazırladın mı?",
                "Farklı yaşlara uygun parçaları karıştırdım.",
                "Ses seviyesini komşuları rahatsız etmeyecek şekilde tutalım.",
                "Akşam ilerledikçe daha da kısarız.",
            ),
            (
                "Pastayı ne zaman teslim alacağız?",
                "Kutlamadan iki saat önce hazır olacak.",
                "Buzdolabında yer açalım.",
                "Üst rafı boşaltabilirim.",
            ),
            (
                "Herkes aynı saatte gelmeyebilir.",
                "Atıştırmalıkları erken gelenler için hazırlarız.",
                "Ana yemeği biraz sonra çıkaralım.",
                "Çoğunluk gelince servis ederiz.",
            ),
            (
                "Hediye yerine ortak bir anı hazırlayalım mı?",
                "Herkesten kısa bir not toplayabiliriz.",
                "Fotoğrafları izinsiz paylaşmayalım.",
                "Yalnızca gönderilen ve onaylananları kullanırız.",
            ),
            (
                "Açık havada kutlama riskli olabilir.",
                "Yağmur ihtimaline karşı kapalı alanı tutalım.",
                "Kararı bir gün önce verelim.",
                "Hava tahminine göre herkese bildiririz.",
            ),
            (
                "Etkinlik sonunda toparlanmayı da planlayalım.",
                "Görevleri baştan paylaşırsak kolay olur.",
                "Ben mutfak tarafını alırım.",
                "Ben de salonu düzenlerim.",
            ),
        ],
        [
            ("Davet saatini net yazalım.", "Yanlış anlaşılmayı önler."),
            ("Yiyecek tercihlerini önceden soralım.", "Alerji ve tercihleri menüye göre düzenleriz."),
            ("Tek kullanımlık ürünleri azaltalım.", "Evdeki tabak ve bardakları kullanırız."),
            ("Çocuklar için sakin bir köşe ayıralım.", "Masa oyunlarını oraya koyabiliriz."),
            ("Bütçeyi aşmadan ilerleyelim.", "Öncelikli kalemleri listeleyelim."),
            ("Ertesi güne iş bırakmayalım.", "Kapanışta on beş dakika toparlarız."),
        ],
    ),
    topic(
        "evcil-hayvan-bakimi",
        "Evcil hayvan bakımı",
        "ev ve veteriner danışması",
        ("birlikte evcil hayvan bakımı yapan kişiler",),
        "polite",
        [
            (
                "Kedinin mama kabı boşalmış.",
                "Ölçülü porsiyonunu şimdi koyabilirim.",
                "Suyunu da tazeleyelim.",
                "Kabı yıkayıp yeniden doldururum.",
            ),
            (
                "Köpeği akşam kim gezdirecek?",
                "İşten erken gelirsem ben çıkarabilirim.",
                "Yağmur olursa kısa rotayı kullanırız.",
                "Havlusunu da kapının yanına koyarız.",
            ),
            (
                "Rutin kontrol için randevu almak istiyorum.",
                "Hafta içi öğleden sonra boşluğumuz var.",
                "Taşıma çantasıyla gelmem uygun olur mu?",
                "Evet, güvenli taşıma için iyi olur.",
            ),
            (
                "Kuşun kafesini temizleme sırası bende mi?",
                "Geçen hafta ben yapmıştım.",
                "Yemlikleri de ben yıkarım.",
                "Ben de temiz kâğıtları hazırlayabilirim.",
            ),
            (
                "Hafta sonu şehir dışında olacağız.",
                "Bakım için güvendiğimiz kişiden destek isteyelim.",
                "Beslenme planını yazılı bırakalım.",
                "Acil durumda ulaşılacak kliniği de ekleriz.",
            ),
            (
                "Yeni oyuncağa hemen alışmadı.",
                "Eski oyuncağının yanına koyup zaman tanıyalım.",
                "Zorlamadan kendisinin yaklaşmasını bekleriz.",
                "Evet, sakin bir ortamda dursun.",
            ),
            (
                "Mama paketini açık bırakmayalım.",
                "Kokusunu ve tazeliğini korumak için kapaklı kaba koyarız.",
                "Kabın etiketini de saklayalım.",
                "İçerik ve tarih bilgisi gerektiğinde elimizde olur.",
            ),
            (
                "Tüylerini tararken huzursuz oluyor.",
                "Kısa aralıklarla ve sakin biçimde deneyebiliriz.",
                "Rahatsızlık sürerse uzmana danışalım.",
                "Evet, tıbbi değerlendirmeyi veterinere bırakırız.",
            ),
        ],
        [
            ("Bakım saatini rutinde tutalım.", "Düzenli olunca takip etmek kolaylaşıyor."),
            (
                "İlaç konusunda yalnızca veteriner önerisini uygulayalım.",
                "Doz veya ürün konusunda kendimiz karar vermeyiz.",
            ),
            ("Kapı açılırken dikkatli olalım.", "Önce hayvanın güvenli odada olduğundan emin oluruz."),
            ("Mama değişimini aniden yapmayalım.", "Geçiş planını veterinerle konuşuruz."),
            ("Taşıma çantasını önceden hazırlayalım.", "İçine tanıdığı bir örtü koyabiliriz."),
            ("Bakım notlarını tek yerde tutalım.", "Tarihleri kısa bir çizelgeye yazarız."),
        ],
    ),
    topic(
        "kutuphane",
        "Kütüphane kullanımı",
        "halk kütüphanesi",
        ("okur-kütüphane hakkında bilgi veren kişi",),
        "polite",
        [
            (
                "Bu kitabın başka baskısı var mı?",
                "Katalogda iki farklı baskı görünüyor.",
                "Yeni baskıyı ödünç almak istiyorum.",
                "Üst kattaki rafta müsait görünüyor.",
            ),
            (
                "Çalışma odası için rezervasyon gerekiyor mu?",
                "İki saatlik kullanım için çevrim içi kayıt yapılıyor.",
                "Bugün öğleden sonra boşluk var mı?",
                "Saat ikide bir oda uygun.",
            ),
            (
                "Ödünç aldığım kitabın süresini uzatabilir miyim?",
                "Başka bir okur ayırtmadıysa uzatılabilir.",
                "Katalogda bekleyen görünmüyor.",
                "Süreyi bir hafta uzattım.",
            ),
            (
                "Sessiz çalışma bölümü hangi katta?",
                "Üçüncü kat tamamen sessiz alan.",
                "Telefon görüşmesi için nereye çıkmalıyım?",
                "Kat girişindeki ortak alanı kullanabilirsiniz.",
            ),
            (
                "Aradığım makaleye erişemiyorum.",
                "Kütüphanenin veri tabanı erişimini kontrol edelim.",
                "Başlığı katalogda buldum ama tam metin açılmıyor.",
                "Erişim kapsamını danışma masasından teyit edebiliriz.",
            ),
            (
                "Kitabı yanlış rafa bırakmış olabilirim.",
                "İade arabasına bırakmanız yeterliydi.",
                "Doğrudan rafa koydum.",
                "Görevliler raf taramasında yerini düzeltebilir.",
            ),
            (
                "Kütüphane kartımı evde unutmuşum.",
                "Dijital kartınız uygulamada bulunabilir.",
                "Kimlik bilgisi paylaşmadan uygulamadan gösterebilirim.",
                "Evet, karekod giriş için yeterli.",
            ),
            (
                "Hafta sonu çalışma saatleri değişiyor mu?",
                "Cumartesi erken kapanıyor, pazar kapalı.",
                "Güncel takvimi nereden takip edebilirim?",
                "Kütüphanenin duyuru sayfasında yayımlanıyor.",
            ),
        ],
        [
            ("Kitabı temiz ellerle kullanacağım.", "Özellikle eski baskılar için önemli."),
            ("Not alırken sayfaları işaretlemeyeyim.", "Ayraç ve ayrı bir defter kullanabilirsiniz."),
            ("Çıkmadan eşyalarımı kontrol edeyim.", "Kayıp eşya durumunu önler."),
            ("Masada yiyecek tüketmeyeyim.", "İçecek için kapaklı şişe kullanılabilir."),
            ("Kaynağın künyesini doğru not edelim.", "Yazar, başlık ve baskı bilgisi yeterli olur."),
            ("Bilgisayarı bırakırken oturumu kapatacağım.", "Ortak cihazlarda bu iyi bir güvenlik adımıdır."),
        ],
    ),
    topic(
        "tamir-ve-servis",
        "Ev eşyası tamiri",
        "ev ve teknik servis",
        ("tamir sürecini planlayan kişiler",),
        "polite",
        [
            (
                "Bulaşık makinesi programın ortasında duruyor.",
                "Ekranda bir uyarı kodu görünüyor mu?",
                "Sadece su ışığı yanıyor.",
                "Kılavuzdaki temel kontrollerden sonra servis planlayabiliriz.",
            ),
            (
                "Musluk yavaşça damlatıyor.",
                "Önce vanayı ve contayı kontrol etmek gerekir.",
                "Su tesisatına kendim müdahale etmeyeyim.",
                "Evet, uygun bir tesisatçıdan randevu alalım.",
            ),
            (
                "Dolap kapağının menteşesi gevşedi.",
                "Uygun tornavidayla vidalar kontrol edilebilir.",
                "Ahşapta çatlak da var gibi.",
                "Zorlamadan bir marangozun görmesi daha doğru olur.",
            ),
            (
                "Servis randevusunu cumaya alabilir miyiz?",
                "Cuma öğleden sonra bir zaman aralığı boş.",
                "Gelmeden önce haber verir misiniz?",
                "Görevli yola çıktığında bildirim gönderilir.",
            ),
            (
                "Cihazın garanti belgesini bulamıyorum.",
                "Satın alma kaydı dijital hesabınızda olabilir.",
                "Seri numarasını açık mesajda paylaşmayacağım.",
                "Doğru, yalnızca resmî servis formunda kullanın.",
            ),
            (
                "Tamir ücretini işlemden önce öğrenebilir miyim?",
                "İncelemeden sonra onayınıza sunulan bir teklif hazırlanır.",
                "Onay vermeden parça değişmesin lütfen.",
                "Bu talebi servis kaydına ekliyorum.",
            ),
            (
                "Duvar rafı biraz eğilmiş.",
                "Üzerindeki ağırlığı hemen azaltalım.",
                "Montajı tekrar kontrol ettirelim.",
                "Güvenli olana kadar rafı kullanmayız.",
            ),
            (
                "Servis sonrası aynı sorun yeniden oldu.",
                "Önceki işlem kaydını açalım.",
                "Aynı belirtiyi kısa bir videoyla belgeledim.",
                "Kişisel alan görünmüyorsa kayda ekleyebilirsiniz.",
            ),
        ],
        [
            ("Elektrik veya gaz işini uzmana bırakalım.", "Bu tür işlemleri kendimiz denemeyiz."),
            ("Randevu saatinde evde biri olacak.", "Yetkili kişiyi servis formuna yazabilirsiniz."),
            ("Değişen parçanın bilgisini isteyelim.", "Servis fişinde parça adı yer alır."),
            ("İşlemden önce eşyaların fotoğrafını çekelim.", "Mevcut durumu belgelemek yararlı olur."),
            ("Çalışma alanını boşaltırım.", "Görevli daha güvenli ve hızlı çalışabilir."),
            ("İş bitince birlikte test edelim.", "Sorunun giderildiğini yerinde doğrularız."),
        ],
    ),
    topic(
        "sinema-ve-etkinlik",
        "Sinema ve etkinlik planı",
        "sinema ve kültür merkezi",
        ("birlikte etkinlik planlayan kişiler",),
        "informal",
        [
            (
                "Bu akşam hangi filme gidelim?",
                "İkimizin de izlemediği komedi uygun olabilir.",
                "Çok geç olmayan seansı seçelim.",
                "Yedi seansı iyi görünüyor.",
            ),
            (
                "Koltukları nereden seçelim?",
                "Orta sıranın kenarları hâlâ boş.",
                "Ekrana çok yakın olmasın.",
                "Altıncı sıra rahat olur.",
            ),
            (
                "Bilet saatini yanlış seçmişim.",
                "Değişim koşuluna uygulamadan bakalım.",
                "Seans başlamadan değiştirebiliyoruz.",
                "O zaman bir sonraki seansa alalım.",
            ),
            (
                "Gösteriden önce ne kadar erken gidelim?",
                "Girişte sıra olursa yirmi dakika iyi olur.",
                "Biletler telefonda hazır.",
                "Yine de parlaklığı önceden açarız.",
            ),
            (
                "Açık hava etkinliğinde yer numarası var mı?",
                "Bilette serbest oturma yazıyor.",
                "Ön sıralar için erken çıkalım.",
                "Kapılar açılmadan biraz önce orada oluruz.",
            ),
            (
                "Altyazılı seans var mı?",
                "Akşamki iki seans altyazılı görünüyor.",
                "Daha sakin olanı seçelim.",
                "Hafta içi son seans daha boş olabilir.",
            ),
            (
                "Etkinlik iptal edilirse nasıl öğreniriz?",
                "Organizatör uygulamadan bildirim gönderiyor.",
                "Duyuruyu çıkmadan kontrol ederiz.",
                "Bilet koşullarına da göz atalım.",
            ),
            (
                "Çıkışta toplu taşıma bulabilir miyiz?",
                "Son metro saatine yetişiyoruz.",
                "Film uzarsa otobüs seçeneğine bakalım.",
                "Dönüş rotasını şimdiden kaydederiz.",
            ),
        ],
        [
            ("Telefonları sessize almayı unutmayalım.", "Salona girmeden kapatırız."),
            ("Yiyecek sırasına girmeyebiliriz.", "Yanımızda su olması yeter."),
            ("Buluşma noktasını netleştirelim.", "Ana girişteki afişin önünde buluşuruz."),
            ("Biletleri ayrı ayrı saklayalım.", "Herkes kendi karekodunu açar."),
            ("Çıkış kalabalığına kalmayalım diye acele etmeyelim.", "Salon boşalınca rahatça çıkarız."),
            ("Film hakkında önceden fazla okumayalım.", "Sürprizleri bozmadan gidelim."),
        ],
    ),
    topic(
        "park-ve-doga",
        "Park ve doğa gezisi",
        "şehir parkı ve yürüyüş alanı",
        ("birlikte park gezisi planlayan kişiler",),
        "informal",
        [
            (
                "Parkta hangi girişte buluşalım?",
                "Gölet tarafındaki giriş daha sakin.",
                "Bisiklet parkı da orada mı?",
                "Evet, kapının hemen yanında.",
            ),
            (
                "Yürüyüş yolunun tamamını yapalım mı?",
                "Bugün kısa halkayı seçebiliriz.",
                "Dizimizi yormadan ilerleyelim.",
                "İstediğimiz yerde mola veririz.",
            ),
            (
                "Piknik masaları dolu olur mu?",
                "Öğle saatinde kalabalıklaşabilir.",
                "Erken gidip gölgeli bir yer bulalım.",
                "Kahvaltıyı da yanımızda götürürüz.",
            ),
            (
                "Köpekler için ayrılmış alan nerede?",
                "Ana yolun sonunda çevrili bir bölüm var.",
                "Tasma kuralını tabeladan kontrol edelim.",
                "Parkın kurallarına göre hareket ederiz.",
            ),
            (
                "Gölette kuşları izlemek istiyorum.",
                "Sabah saatleri daha sakin oluyor.",
                "Uzaktan izleyip beslemeyelim.",
                "Doğal düzeni bozmadan fotoğraf çekeriz.",
            ),
            (
                "Çocuk oyun alanı güneşte kalıyor mu?",
                "Bir bölümü ağaç gölgesinde.",
                "Öğleden önce gitmek daha iyi olur.",
                "Su ve şapka da alırız.",
            ),
            (
                "Parkta su çeşmesi çalışıyor mu?",
                "Son gidişimde ana girişteki açıktı.",
                "Yine de şişeleri evde dolduralım.",
                "Çeşmeyi yedek olarak düşünürüz.",
            ),
            (
                "Hava kararmadan dönelim.",
                "Gün batımından bir saat önce çıkışa yöneliriz.",
                "Aydınlatılmış ana yoldan gidelim.",
                "Patikalara sapmadan ilerleriz.",
            ),
        ],
        [
            ("Çöpümüzü yanımızda çıkaralım.", "Küçük bir atık poşeti alırım."),
            ("Yüksek sesle müzik açmayalım.", "Parkın sakinliğini koruruz."),
            ("Bitkilere zarar vermeden yürüyelim.", "İşaretli yollardan ayrılmayız."),
            ("Banklar ıslak olabilir.", "Oturmak için küçük bir örtü alırız."),
            ("Tuvaletlerin yerini girişte soralım.", "Haritadan da kontrol edebiliriz."),
            ("Dönüşte araç saatine bakalım.", "Çıkışa yaklaşınca kontrol ederiz."),
        ],
    ),
    topic(
        "berber-ve-kuafor",
        "Berber ve kuaför randevusu",
        "kuaför salonu",
        ("müşteri-kuaför çalışanı",),
        "polite",
        [
            (
                "Yarın için saç kesimi randevusu var mı?",
                "Öğleden sonra iki boş saatimiz bulunuyor.",
                "Dört civarı benim için uygun.",
                "Saat dörde kaydınızı oluşturabilirim.",
            ),
            (
                "Randevuma biraz gecikeceğim.",
                "Ne kadar gecikeceğinizi biliyor musunuz?",
                "On dakika içinde orada olurum.",
                "Tamam, sıranızı koruyabiliriz.",
            ),
            (
                "Saçımı çok kısaltmadan uçlarını aldırmak istiyorum.",
                "İstediğiniz uzunluğu başlamadan birlikte belirleriz.",
                "Ön taraftan az, arkadan biraz daha alınabilir.",
                "Aynada göstererek adım adım ilerleriz.",
            ),
            (
                "Bu işlem yaklaşık ne kadar sürer?",
                "Saçın uzunluğuna göre kırk dakika kadar.",
                "Sonraki randevuma yetişmem gerekiyor.",
                "Başlangıçta saati tekrar netleştiririz.",
            ),
            (
                "Kullandığınız ürünün kokusu yoğun mu?",
                "Kokusuz bir alternatifimiz var.",
                "Mümkünse onu tercih ederim.",
                "Talebinizi not edip o ürünü kullanırız.",
            ),
            (
                "Randevuyu başka bir güne alabilir miyiz?",
                "Çarşamba aynı saatte boşluk var.",
                "Çarşamba daha uygun olur.",
                "Kaydınızı o güne taşıdım.",
            ),
            (
                "Çocuk için de kesim yapılıyor mu?",
                "Evet, kısa randevu aralıklarımız var.",
                "Sakin bir saat seçebilir miyiz?",
                "Sabah ilk saat genellikle daha sessiz.",
            ),
            (
                "Ödeme seçeneklerini öğrenebilir miyim?",
                "Kart ve nakit kabul ediyoruz.",
                "Temassız ödeme kullanacağım.",
                "İşlem sonunda kasadan yapabilirsiniz.",
            ),
        ],
        [
            ("Başlamadan önce fiyatı netleştirelim.", "Uygulanacak işlemleri tek tek belirtiriz."),
            ("Beklerken dışarı çıkabilir miyim?", "Sıranız yaklaşınca haber verebiliriz."),
            ("Çantamı güvenli bir yere bırakabilir miyim?", "Yanınızdaki askılı bölümü kullanabilirsiniz."),
            ("Fotoğraf yerine sözlü tarif edeceğim.", "İstediğiniz görünümü birlikte netleştiririz."),
            ("Randevu hatırlatması geliyor mu?", "Bir gün önce kısa bildirim gönderiyoruz."),
            ("Salonda havalandırma açık mı?", "Gün boyunca düzenli havalandırıyoruz."),
        ],
    ),
    topic(
        "kahvalti-plani",
        "Kahvaltı planı",
        "ev ve kahvaltı mekânı",
        ("birlikte kahvaltı planlayan kişiler",),
        "informal",
        [
            (
                "Yarın kahvaltıyı evde yapalım mı?",
                "Olur, malzemeleri akşamdan hazırlayalım.",
                "Ben ekmek ve meyve alırım.",
                "Ben de peynirle yumurtayı kontrol ederim.",
            ),
            (
                "Kahvaltıya kaçta buluşalım?",
                "On gibi herkes uyanmış olur.",
                "Çok geç kalmadan başlayalım.",
                "Dokuz buçukta masayı kurarız.",
            ),
            (
                "Dışarıda sakin bir kahvaltı yeri biliyor musun?",
                "Ara sokaktaki küçük mekân sabahları sessiz.",
                "Önceden yer ayırtmak gerekir mi?",
                "Hafta sonuysa aramak iyi olur.",
            ),
            (
                "Çayı kim demleyecek?",
                "Ben demleyebilirim, sen sofrayı kur.",
                "Açık içenler için sıcak su da olsun.",
                "Küçük demliği ayrı hazırlarım.",
            ),
            (
                "Sıcak bir şey de yapalım mı?",
                "Sebzeli omlet hızlı olur.",
                "Biberi az koyalım.",
                "Herkesin yiyebileceği gibi hazırlarız.",
            ),
            (
                "Kahvaltı çok ağır olmasın.",
                "Meyve, yoğurt ve tost yeterli olabilir.",
                "Porsiyonları küçük tutalım.",
                "İsteyen sonradan ekler.",
            ),
            (
                "Misafirlerden biri erken gelecek.",
                "Kahveyi hazır edip bekletebiliriz.",
                "Masayı da önceden kuralım.",
                "Eksik kalırsa birlikte tamamlarız.",
            ),
            (
                "Kalan ekmekleri değerlendirelim.",
                "Fırında kıtır ekmek yapabiliriz.",
                "Baharatı ayrı kullanalım.",
                "Bir kısmını sade bırakırız.",
            ),
        ],
        [
            ("Bulaşıkları sırayla toplarız.", "Kimseye fazla iş kalmaz."),
            ("Alışveriş listesini kısa tutalım.", "Evdekileri kontrol edip yalnızca eksiği alırız."),
            ("Masaya sürahiyle su koyalım.", "Herkes kolayca ulaşır."),
            ("Yiyecekleri uzun süre dışarıda bırakmayalım.", "Servis bitince uygun şekilde kaldırırız."),
            ("Müzik çok yüksek olmasın.", "Sabah için sakin bir liste açarız."),
            ("Pencereyi biraz açalım.", "Mutfak daha ferah olur."),
        ],
    ),
    topic(
        "telefon-gorusmesi",
        "Günlük telefon görüşmesi",
        "ev ve şehir içi yaşam",
        ("telefonla görüşen tanışıklar",),
        "informal",
        [
            (
                "Şu an konuşmak için uygun musun?",
                "Beş dakikam var, sonra toplantıya gireceğim.",
                "O zaman kısa anlatayım.",
                "Tamam, seni dinliyorum.",
            ),
            (
                "Sesin biraz uzaktan geliyor.",
                "Kulaklığın bağlantısı değişmiş olabilir.",
                "Hoparlöre geçince daha iyi mi?",
                "Evet, şimdi daha net.",
            ),
            (
                "Akşam seni tekrar arayayım mı?",
                "Sekizden sonra evde olacağım.",
                "Dokuz çok geç olur mu?",
                "Hayır, o saatte rahat konuşuruz.",
            ),
            (
                "Aradığını gördüm ama dönememiştim.",
                "Sorun değil, acil bir konu değildi.",
                "Şimdi vaktim var.",
                "O zaman hafta sonu planını konuşalım.",
            ),
            (
                "Bağlantı sürekli kesiliyor.",
                "Mesajlaşarak devam edebiliriz.",
                "Önemli noktaları yazayım.",
                "Ben de uygun olduğumda yanıtlarım.",
            ),
            (
                "Seni yanlış zamanda mı aradım?",
                "Dışarıdayım ama kısa konuşabilirim.",
                "Detayları sonra konuşuruz.",
                "Akşam sana ben dönerim.",
            ),
            (
                "Grup aramasına katılabilecek misin?",
                "Başlangıca yetişemem ama sonra bağlanırım.",
                "Kararları başta konuşacağız.",
                "Önceden fikrimi gruba yazarım.",
            ),
            (
                "Numaranı birine vermemi istemişlerdi.",
                "Önce kim olduğunu bana sorar mısın?",
                "İznin olmadan paylaşmayacağım.",
                "Teşekkürler, iletişimi kendim kurarım.",
            ),
        ],
        [
            ("Kişisel ayrıntıları kalabalıkta konuşmayalım.", "Daha sakin bir zamanda devam ederiz."),
            ("Kapanmadan saati netleştirelim.", "Takvime ikimiz de ekleriz."),
            ("Unutmamak için kısa not alacağım.", "Yalnızca gerekli maddeleri yaz."),
            ("Telefonun şarjı azalıyor.", "Görüşmeyi uzatmadan tamamlayalım."),
            ("Bir dosya göndermem gerekiyor.", "Güvendiğimiz kanaldan sonra paylaşabilirsin."),
            ("Yanlış anlaşılmasın diye son kararı yazılı iletelim.", "Konuşma sonrası kısa özet göndeririz."),
        ],
    ),
    topic(
        "cocuklarla-gun",
        "Çocuklarla günlük plan",
        "ev ve çocuk etkinlik alanı",
        ("çocukların günlük planını konuşan yetişkinler",),
        "polite",
        [
            (
                "Çocuklarla bugün ne yapalım?",
                "Evde boyama ve sonra park iyi olabilir.",
                "Hava bozarsa evde kalırız.",
                "İki seçenek için de malzemeyi hazırlarız.",
            ),
            (
                "Atölyenin yaş grubu uygun mu?",
                "Etkinlik dört yaş ve üzeri için hazırlanmış.",
                "Bir yetişkin yanında kalabiliyor mu?",
                "Evet, ilk bölümde eşlik edebilirsiniz.",
            ),
            (
                "Uyku saatini çok geciktirmeyelim.",
                "Etkinlikten altıda ayrılırsak yetişiriz.",
                "Dönüşte yemek hazır olsun.",
                "Önceden kolay bir şey hazırlayabiliriz.",
            ),
            (
                "Oyuncakları toplama işini oyuna çevirelim mi?",
                "Renklerine göre kutulara ayırabiliriz.",
                "Süre tutmak eğlenceli olabilir.",
                "Acele ettirmeden kısa bir şarkı açarız.",
            ),
            (
                "Bugün ekran süresini nasıl planlayalım?",
                "Ödev ve dışarıdaki oyundan sonra kısa tutabiliriz.",
                "Süreyi baştan söyleyelim.",
                "Bittiğinde başka etkinliğe geçeriz.",
            ),
            (
                "Yanımıza yedek kıyafet alalım mı?",
                "Parkta oynayacaklarsa iyi olur.",
                "Küçük çantaya bir takım koyarım.",
                "Su ve mendili de ekleriz.",
            ),
            (
                "Kitap okumak için hangisini seçelim?",
                "Kısa ve resimli olanı kendileri seçsin.",
                "Aynı kitabı tekrar isterlerse sorun değil.",
                "Sevdikleri hikâyeyi tekrarlamak keyifli olabilir.",
            ),
            (
                "Kalabalık yerde buluşma noktasını belirleyelim.",
                "Girişteki danışma tabelası kolay bulunur.",
                "Çocuklara da basitçe anlatalım.",
                "Ayrı kalırlarsa görevliye gitmelerini söyleriz.",
            ),
        ],
        [
            ("Atıştırmalığı küçük porsiyon yapalım.", "Yanına su da koyarız."),
            ("Etkinlik arasında dinlenme zamanı bırakalım.", "Çok yorulmadan günü tamamlarlar."),
            ("Fotoğraf paylaşmadan önce izin alalım.", "Diğer çocukların görünmediğinden emin oluruz."),
            ("Kuralları kısa ve açık anlatalım.", "Bir seferde tek beklenti söylemek kolay olur."),
            ("Gürültü artarsa sakin bir köşeye geçeriz.", "Kısa mola iyi gelebilir."),
            ("Dönüş saatini değiştirmeyelim.", "Rutinleri korunmuş olur."),
        ],
    ),
    topic(
        "bahce-ve-bitki",
        "Bahçe ve bitki bakımı",
        "ev balkonu ve ortak bahçe",
        ("bitki bakımı hakkında konuşan kişiler",),
        "polite",
        [
            (
                "Balkon için gölgeyi seven bir bitki arıyorum.",
                "Bu bölümde doğrudan güneş istemeyen türler var.",
                "Bakımı kolay olanı tercih ederim.",
                "Etiketindeki ışık ve sulama bilgisine birlikte bakalım.",
            ),
            (
                "Saksının toprağı çok çabuk kuruyor.",
                "Konumu ve drenajını kontrol etmek iyi olur.",
                "Öğle güneşini doğrudan alıyor.",
                "Daha korunaklı bir yere taşımayı deneyebilirsiniz.",
            ),
            (
                "Bitkileri hafta sonu kim sulayacak?",
                "Cumartesi ben, pazar sen bakabilirsin.",
                "Toprağı kontrol etmeden su vermeyelim.",
                "Evet, her saksının ihtiyacı farklı olabilir.",
            ),
            (
                "Fesleğeni daha büyük saksıya alalım mı?",
                "Kökleri alttan görünmeye başladıysa zamanı gelmiş olabilir.",
                "Bir boy büyük saksı yeterli mi?",
                "Çok büyük seçmeden kademeli geçmek iyi olur.",
            ),
            (
                "Ortak bahçedeki kuru yaprakları toplayalım.",
                "Kompost için ayrı bir torba kullanabiliriz.",
                "Hastalıklı görünenleri ayıralım.",
                "Onları görevliye gösterip ayrı tutarız.",
            ),
            (
                "Yeni fideleri ne zaman dikelim?",
                "Öğle sıcağı yerine akşamüstü daha uygun.",
                "Toprağı önceden nemlendirelim.",
                "Dikim sonrası hafifçe sulayabiliriz.",
            ),
            (
                "Bu yaprakların kenarı sararmış.",
                "Tek bir nedene bağlamadan ışık ve sulamayı gözlemleyelim.",
                "Bir hafta not tutayım.",
                "Değişim sürerse bir uzmana danışabilirsiniz.",
            ),
            (
                "Sulama kabını ortak alanda bırakabilir miyiz?",
                "Geçişi engellemeyen raf uygun.",
                "Üzerine ortak kullanım etiketi koyalım.",
                "Böylece yanlışlıkla alınmaz.",
            ),
        ],
        [
            ("Bitki bakım ürününü etikete göre kullanalım.", "Önerilen miktarı aşmayız."),
            ("Sabah erken bakım yapmak daha serin olur.", "Güneş yükselmeden bitirebiliriz."),
            ("Suyu israf etmeden sulayalım.", "Yavaş döküp toprağın emmesini bekleriz."),
            ("Saksı altındaki suyu kontrol edelim.", "Uzun süre birikmesine izin vermeyiz."),
            ("Yeni bitkiyi diğerlerinden ayrı gözlemleyelim.", "Bir süre uyumunu takip ederiz."),
            ("Bakım tarihlerini küçük etikete yazalım.", "Ne zaman işlem yaptığımız karışmaz."),
        ],
    ),
    topic(
        "resmi-islemler",
        "Günlük resmî işlemler",
        "belediye hizmet noktası",
        ("başvuru sahibi-resmî işlem hakkında bilgi veren kişi",),
        "formal",
        [
            (
                "Başvuru için randevu gerekiyor mu?",
                "Bu işlemde çevrim içi randevu öncelikli.",
                "Bugün sıra alarak işlem yapabilir miyim?",
                "Kontenjan varsa danışmadan sıra veriliyor.",
            ),
            (
                "Formda eksik belge uyarısı görüyorum.",
                "Belge listesini başvuru türüyle karşılaştıralım.",
                "İkamet belgesi eksik görünüyor.",
                "Resmî portal üzerinden güncel kopyayı ekleyebilirsiniz.",
            ),
            (
                "Başvurunun durumunu nasıl takip edebilirim?",
                "Takip ekranında başvuru numarasıyla görüntüleniyor.",
                "Numarayı açık mesajda paylaşmayacağım.",
                "Doğru, yalnızca resmî ekranda kullanmanız gerekir.",
            ),
            (
                "Belgenin ıslak imzalı olması gerekiyor mu?",
                "İşlem yönergesinde kabul edilen biçimler yazıyor.",
                "Güncel yönergeyi birlikte kontrol edebilir miyiz?",
                "Evet, resmî sayfadaki son sürüme bakalım.",
            ),
            (
                "Randevu saatine yetişemeyebilirim.",
                "Sistemden iptal edip uygun bir saate taşıyabilirsiniz.",
                "Aynı gün için başka boşluk var mı?",
                "Öğleden sonra bir kontenjan görünüyor.",
            ),
            (
                "Ücretin hangi kanaldan ödendiğini öğrenmek istiyorum.",
                "Yalnızca resmî ödeme ekranındaki yöntemleri kullanın.",
                "Gișede kart kabul ediliyor mu?",
                "Hizmet noktasının güncel bilgisini danışmadan teyit edebilirsiniz.",
            ),
            (
                "Başvuruyu vekâleten yapmak mümkün mü?",
                "Gerekli yetki belgesi işlem türüne göre değişiyor.",
                "Listeyi önceden inceleyeyim.",
                "Eksik evrakla gelmemiş olursunuz.",
            ),
            (
                "Sonuç belgesini nereden alacağım?",
                "Onaylanınca dijital belge bölümünde açılacak.",
                "Basılı kopya da gerekli olabilir.",
                "Gerekirse hizmet noktasından onaylı kopya talep edebilirsiniz.",
            ),
        ],
        [
            ("Kişisel bilgilerimi yalnızca resmî forma gireceğim.", "Güvenli yaklaşım budur."),
            ("Belge tarihlerini tekrar kontrol edelim.", "Süresi geçmiş bir evrak kalmasın."),
            ("Gönderimden önce önizlemeyi açalım.", "Yanlış dosya yüklenmediğini doğrularız."),
            ("Başvuru belgesinin kopyasını saklayacağım.", "Takip sürecinde yararlı olabilir."),
            ("Resmî alan adını kontrol edelim.", "Benzer görünen sahte sayfalardan kaçınırız."),
            ("İşlem süresinin tahmini olduğunu not edelim.", "Kesin sonuç tarihi gibi değerlendirmeyiz."),
        ],
    ),
)


OPENERS = {
    "informal": (
        "",
        "Selam, ",
        "Bir şey soracağım; ",
        "Müsaitsen, ",
        "Bu arada, ",
        "Şunu konuşalım: ",
        "Kısa bir şey var; ",
        "Aklıma gelmişken, ",
    ),
    "polite": (
        "",
        "Merhaba, ",
        "Kolay gelsin, ",
        "Bir şey danışacaktım; ",
        "Müsaitseniz, ",
        "Kısa bir sorum var: ",
        "Rica etsem, ",
        "Bir konuda yardım rica edeceğim: ",
    ),
    "formal": (
        "",
        "Merhaba, ",
        "İyi günler, ",
        "Kısa bir konuda bilgi rica edeceğim: ",
        "Müsaitseniz, ",
        "Şunu netleştirmek isterim: ",
        "Gündemle ilgili olarak, ",
        "Uygunsanız, ",
    ),
}

STATEMENT_OPENERS = {
    "informal": ("", "Selam, ", "Bu arada, ", "Şunu konuşalım: ", "Kısa bir şey var; ", "Aklıma gelmişken, "),
    "polite": ("", "Merhaba, ", "Kolay gelsin, ", "Bir şey danışacaktım; ", "Bir konuda yardım rica edeceğim: "),
    "formal": (
        "",
        "Merhaba, ",
        "İyi günler, ",
        "Şunu netleştirmek isterim: ",
        "Gündemle ilgili olarak, ",
        "Kısaca durumu paylaşayım: ",
    ),
}

MULTI_TOPIC_OPENERS = {
    "informal": (
        "Birkaç şeyi sırayla netleştirelim; ilk sorum şu: ",
        "Hazır konuşuyorken birkaç ayrıntıyı aradan çıkaralım: ",
        "Aklımda birkaç küçük soru var; ilki şu: ",
        "Planı toparlamak için ilk olarak şunu sorayım: ",
        "Birkaç konu birikmiş; ilkinden başlayalım: ",
        "Vaktimiz varken birkaç şeyi birlikte konuşalım: ",
        "Kısa kısa birkaç şey soracağım; ilki şu: ",
        "Sonradan karışmasın diye önce şunu netleştirelim: ",
        "Bugünkü planla ilgili ilk sorum şu: ",
        "Karar vermeden önce bir ayrıntıyı netleştirelim: ",
        "Şimdi uygunken ilk sorumu sorayım: ",
        "Birden fazla ayrıntı var; ilkinden başlayalım: ",
    ),
    "polite": (
        "Birkaç kısa konuyu netleştirmek istiyorum; ilk sorum şu: ",
        "Hazır buradayken birkaç ayrıntıyı netleştirebilir miyiz: ",
        "Plan yaparken birkaç soru oluştu; ilki şu: ",
        "Birbiriyle ilgili birkaç şeyi sırayla soracağım; ilki şu: ",
        "İşlemi tamamlamadan önce ilk sorumu ileteyim: ",
        "Müsaitseniz birkaç sorumu sırayla ileteceğim; ilki şu: ",
        "Aklımdaki kısa sorulardan ilki şu: ",
        "Kısaca birkaç noktayı teyit etmek istiyorum; ilk sorum şu: ",
        "Bugünkü plan için ilk olarak şunu sorayım: ",
        "Karar vermeden önce bir ayrıntıyı daha öğrenebilir miyim: ",
        "Uygunsanız ilk sorumu ileteyim: ",
        "Birkaç ayrıntı birikti; ilkinden başlayabilir miyiz: ",
    ),
    "formal": (
        "Birbiriyle ilgili birkaç noktayı netleştirmek istiyorum; ilk sorum şu: ",
        "Süreci tamamlamadan önce ilk sorumu ileteyim: ",
        "Planlama için gereken ilk ayrıntıyı teyit edebilir miyiz: ",
        "Gündemdeki ilk maddeyi ele alabilir miyiz: ",
        "İşleme devam etmeden önce ilk sorumu ileteyim: ",
        "Uygunsanız birkaç sorumu sırasıyla ileteceğim; ilki şu: ",
        "Açık kalan kısa sorulardan ilki şöyledir: ",
        "Karar öncesinde ilk olarak şu noktayı doğrulayalım: ",
        "Bugünkü plan açısından ilk sorum şöyledir: ",
        "Sonraki adıma geçmeden bir ayrıntıyı daha görüşebilir miyiz: ",
        "Müsaitseniz ilk sorumu yönelteyim: ",
        "Birden fazla soru bulunuyor; ilkinden başlayalım: ",
    ),
}

MULTI_STATEMENT_OPENERS = {
    "informal": (
        "Birkaç şeyi birlikte konuşalım: ",
        "İlk olarak şunu söyleyeyim: ",
        "Şöyle başlayayım: ",
        "Önce şu konudan başlayalım: ",
        "Bir iki ayrıntı var; ilki şu: ",
        "Hazır konuşuyorken şunu da söyleyeyim: ",
        "Aklımdaki ilk konu şu: ",
        "Birden fazla konu var; ilkinden başlayalım: ",
    ),
    "polite": (
        "Birbiriyle ilgili birkaç noktayı paylaşayım; ilki şu: ",
        "Önce şu ayrıntıdan başlayayım: ",
        "Kısaca şu konudan başlayayım: ",
        "Bir iki noktayı birlikte konuşalım; ilki şu: ",
        "Paylaşmak istediğim birkaç ayrıntı var; ilki şu: ",
        "İlk olarak şu durumu belirteyim: ",
        "Şu konudan başlayabilir miyiz: ",
        "Birkaç ayrıntı var; ilkinden başlayayım: ",
    ),
    "formal": (
        "Birbiriyle ilgili birkaç noktayı paylaşayım; ilki şu: ",
        "Sürece ilişkin ilk ayrıntı şu: ",
        "Önce şu konudan başlayayım: ",
        "Gündemdeki ilk madde şu: ",
        "İlk olarak şu durumu paylaşayım: ",
        "Kısaca ilk noktayı belirteyim: ",
        "Şu konuyu önce ele alalım: ",
        "Birden fazla ayrıntı bulunuyor; ilkinden başlayalım: ",
    ),
}

QUESTION_MARKERS = (
    "",
    "Peki, ",
    "Bir de ",
    "Bu arada, ",
    "O hâlde, ",
    "Şunu da netleştirelim: ",
    "Tamam, ",
    "Anladım; ",
)

STATEMENT_MARKERS = (
    "",
    "Bu arada, ",
    "Anladım; ",
)

CONSEQUENCE_MARKERS = {
    "o hâlde",
    "bu durumda",
    "öyleyse",
    "buna göre",
}

DISCOURSE_STARTERS = {
    ("tamam",),
    ("peki",),
    ("anladım",),
    ("bu", "arada"),
    ("o", "hâlde"),
    ("o", "zaman"),
    ("bu", "durumda"),
    ("öyleyse",),
    ("buna", "göre"),
}


def normalized_words(text: str) -> list[str]:
    """Return punctuation-free, Unicode-aware words for marker checks."""
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("\u0307", "")
    return re.findall(r"\w+", normalized, flags=re.UNICODE)


def marker_is_compatible(prefix: str, sentence: str) -> bool:
    """Reject discourse markers that would create an immediate repetition.

    The source library contains natural turn-initial markers of its own. A
    generated prefix must not yield constructions such as ``Tamam, tamam`` or
    stack a consequence marker on a sentence that already says ``o zaman``.
    """
    if not prefix:
        return True
    prefix_words = normalized_words(prefix)
    sentence_words = normalized_words(sentence)
    if not prefix_words or not sentence_words:
        return True
    if prefix_words[0] == sentence_words[0]:
        return False
    prefix_phrase = " ".join(prefix_words)
    sentence_phrase = " ".join(sentence_words)
    prefix_is_discourse = any(tuple(prefix_words[: len(starter)]) == starter for starter in DISCOURSE_STARTERS)
    sentence_is_discourse = any(tuple(sentence_words[: len(starter)]) == starter for starter in DISCOURSE_STARTERS)
    if prefix_is_discourse and sentence_is_discourse:
        return False
    return not (prefix_phrase in CONSEQUENCE_MARKERS and "o zaman" in sentence_phrase)


def lower_initial(text: str) -> str:
    if not text:
        return text
    mapping = {"I": "ı", "İ": "i"}
    return mapping.get(text[0], text[0].lower()) + text[1:]


def attach(prefix: str, sentence: str) -> str:
    return sentence if not prefix or not marker_is_compatible(prefix, sentence) else prefix + lower_initial(sentence)


def records_for_topic(topic_index: int) -> int:
    """Spread 5,000 rows over 35 topics with a maximum count delta of one."""
    base, remainder = divmod(RECORD_COUNT, len(TOPICS))
    return base + (1 if topic_index < remainder else 0)


def scenario_family_count(spec: TopicSpec) -> int:
    # Eight authored four-turn cores plus every ordered pair of the six
    # topic-specific two-turn exchanges: 8 + (6 * 5) = 38 families.
    count = len(spec.cores) + len(spec.addons) * (len(spec.addons) - 1)
    if count != SCENARIO_FAMILIES_PER_TOPIC:
        raise RuntimeError(f"topic {spec.slug} defines {count} scenario families, expected 38")
    return count


def scenario_family_index(spec: TopicSpec, row_index: int) -> int:
    return row_index % scenario_family_count(spec)


def select_split(topic_index: int, row_index: int) -> str:
    """Assign complete scenario families to one split to prevent template leakage."""
    spec = TOPICS[topic_index]
    family_index = scenario_family_index(spec, row_index)
    bucket = (family_index * 7 + topic_index * 3 + SEED) % scenario_family_count(spec)
    if TRAIN_FAMILIES_PER_TOPIC <= bucket < TRAIN_FAMILIES_PER_TOPIC + VALIDATION_FAMILIES_PER_TOPIC:
        return "validation"
    if bucket >= TRAIN_FAMILIES_PER_TOPIC + VALIDATION_FAMILIES_PER_TOPIC:
        return "test"
    return "train"


def base_family(spec: TopicSpec, family_index: int) -> tuple[list[str], set[int]]:
    if family_index < len(spec.cores):
        return list(spec.cores[family_index]), set()

    addon_count = len(spec.addons)
    ordered_pair_index = family_index - len(spec.cores)
    first = ordered_pair_index // (addon_count - 1)
    second = ordered_pair_index % (addon_count - 1)
    if second >= first:
        second += 1
    return [*spec.addons[first], *spec.addons[second]], {first, second}


def render_dialogue(spec: TopicSpec, topic_index: int, row_index: int) -> list[dict[str, str]]:
    family_index = scenario_family_index(spec, row_index)
    repeat_index = row_index // scenario_family_count(spec)
    turns, used_addons = base_family(spec, family_index)
    turn_pattern = (4, 6, 8, 6, 8)
    target_turns = turn_pattern[(row_index * 7 + topic_index + SEED) % len(turn_pattern)]
    first_is_question = turns[0].endswith("?")
    if used_addons or target_turns > 4:
        opener_pool = (
            MULTI_TOPIC_OPENERS[spec.formality] if first_is_question else MULTI_STATEMENT_OPENERS[spec.formality]
        )
    else:
        opener_pool = OPENERS[spec.formality] if first_is_question else STATEMENT_OPENERS[spec.formality]
    style_index = (repeat_index + family_index * 3 + topic_index + SEED) % len(opener_pool)
    turns[0] = attach(opener_pool[style_index], turns[0])
    markers = QUESTION_MARKERS if turns[2].endswith("?") else STATEMENT_MARKERS
    turns[2] = attach(markers[(row_index * 3 + topic_index + SEED) % len(markers)], turns[2])

    addon_indices = [index for index in range(len(spec.addons)) if index not in used_addons]
    offset = (family_index * 3 + topic_index + repeat_index + SEED) % len(addon_indices)
    addon_indices = addon_indices[offset:] + addon_indices[:offset]

    if used_addons and target_turns >= 6:
        # Combination families already draw from the small addon pool. Extend
        # them with a topic core exchange first, preventing reordered addon sets
        # from becoming near duplicates.
        core_extension = spec.cores[(family_index + repeat_index) % len(spec.cores)]
        turns.extend(core_extension[:2])
        if target_turns == 8:
            turns.extend(spec.addons[addon_indices[0]])
    elif target_turns >= 6:
        turns.extend(spec.addons[addon_indices[0]])
        if target_turns == 8:
            turns.extend(spec.addons[addon_indices[1]])

    roles = ("user", "assistant")
    return [{"role": roles[i % 2], "content": text} for i, text in enumerate(turns)]


def generate_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for topic_index, spec in enumerate(TOPICS):
        for row_index in range(records_for_topic(topic_index)):
            messages = render_dialogue(spec, topic_index, row_index)
            split = select_split(topic_index, row_index)
            family_index = scenario_family_index(spec, row_index)
            records.append(
                {
                    "conversation_id": f"trdd5k-{spec.slug}-{row_index + 1:03d}",
                    "messages": messages,
                    "topic": spec.title,
                    "setting": spec.setting,
                    "relationship": spec.relationships[(row_index + topic_index) % len(spec.relationships)],
                    "formality": spec.formality,
                    "turn_count": len(messages),
                    "language": "tr",
                    "synthetic": True,
                    "split": split,
                    "source": {
                        "type": "synthetic",
                        "method": "ai-assisted-scenario-library-deterministic-composition",
                        "generator": "scripts/generate_dataset.py",
                        "generator_version": GENERATOR_VERSION,
                        "seed": SEED,
                        "record_seed": SEED + topic_index * 100_003 + row_index * 997,
                        "scenario_family": family_index,
                        "external_sources": False,
                        "ai_assisted_authoring": True,
                        "runtime_model_inference": False,
                    },
                }
            )

    if len(records) != RECORD_COUNT:
        raise RuntimeError(f"expected {RECORD_COUNT:,} records, generated {len(records):,}")
    ids = {record["conversation_id"] for record in records}
    if len(ids) != len(records):
        raise RuntimeError("duplicate conversation_id generated")
    texts = {json.dumps(record["messages"], ensure_ascii=False, sort_keys=True) for record in records}
    if len(texts) != len(records):
        raise RuntimeError("duplicate conversation generated")
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def write_parquet(path: Path, records: list[dict[str, Any]]) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - exercised in dependency-free environments
        raise RuntimeError("Parquet output requires pyarrow; install the parquet optional dependency") from exc

    schema = pa.schema(
        [
            pa.field("conversation_id", pa.string(), nullable=False),
            pa.field(
                "messages",
                pa.list_(
                    pa.struct(
                        [
                            pa.field("role", pa.string(), nullable=False),
                            pa.field("content", pa.string(), nullable=False),
                        ]
                    )
                ),
                nullable=False,
            ),
            pa.field("topic", pa.string(), nullable=False),
            pa.field("setting", pa.string(), nullable=False),
            pa.field("relationship", pa.string(), nullable=False),
            pa.field("formality", pa.string(), nullable=False),
            pa.field("turn_count", pa.int16(), nullable=False),
            pa.field("language", pa.string(), nullable=False),
            pa.field("synthetic", pa.bool_(), nullable=False),
            pa.field("split", pa.string(), nullable=False),
            pa.field(
                "source",
                pa.struct(
                    [
                        pa.field("type", pa.string(), nullable=False),
                        pa.field("method", pa.string(), nullable=False),
                        pa.field("generator", pa.string(), nullable=False),
                        pa.field("generator_version", pa.string(), nullable=False),
                        pa.field("seed", pa.int32(), nullable=False),
                        pa.field("record_seed", pa.int64(), nullable=False),
                        pa.field("scenario_family", pa.int16(), nullable=False),
                        pa.field("external_sources", pa.bool_(), nullable=False),
                        pa.field("ai_assisted_authoring", pa.bool_(), nullable=False),
                        pa.field("runtime_model_inference", pa.bool_(), nullable=False),
                    ]
                ),
                nullable=False,
            ),
        ]
    )
    table = pa.Table.from_pylist(records, schema=schema)
    pq.write_table(table, path, compression="zstd", version="2.6", write_statistics=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_entry(root: Path, path: Path, records: int | None, media_type: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "records": records,
        "media_type": media_type,
    }


def write_topic_split_samples(root: Path, records: list[dict[str, Any]]) -> Path:
    samples: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record["topic"], record["split"])
        if key not in seen:
            seen.add(key)
            samples.append(record)
    expected = len(TOPICS) * 3
    if len(samples) != expected:
        raise RuntimeError(f"expected {expected} topic/split samples, got {len(samples)}")
    path = root / "samples" / "topic-split-samples.jsonl"
    write_jsonl(path, samples)
    return path


def write_topic_turn_samples(root: Path, records: list[dict[str, Any]]) -> Path:
    samples: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for record in records:
        key = (record["topic"], record["turn_count"])
        if key not in seen:
            seen.add(key)
            samples.append(record)
    expected = len(TOPICS) * 3
    if len(samples) != expected:
        raise RuntimeError(f"expected {expected} topic/turn samples, got {len(samples)}")
    path = root / "samples" / "topic-turn-samples.jsonl"
    write_jsonl(path, samples)
    return path


def build(output_root: Path, formats: tuple[str, ...]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "data").mkdir(exist_ok=True)
    (output_root / "samples").mkdir(exist_ok=True)
    records = generate_records()
    artifacts: list[dict[str, Any]] = []

    by_split = {split: [r for r in records if r["split"] == split] for split in ("train", "validation", "test")}
    if "jsonl" in formats:
        all_path = output_root / "data" / "all.jsonl"
        count = write_jsonl(all_path, records)
        artifacts.append(artifact_entry(output_root, all_path, count, "application/x-ndjson"))
        for split, split_records in by_split.items():
            path = output_root / "data" / f"{split}.jsonl"
            count = write_jsonl(path, split_records)
            artifacts.append(artifact_entry(output_root, path, count, "application/x-ndjson"))

    if "parquet" in formats:
        for split, split_records in by_split.items():
            path = output_root / "data" / f"{split}.parquet"
            write_parquet(path, split_records)
            artifacts.append(artifact_entry(output_root, path, len(split_records), "application/vnd.apache.parquet"))

    sample_path = write_topic_split_samples(output_root, records)
    artifacts.append(artifact_entry(output_root, sample_path, len(TOPICS) * 3, "application/x-ndjson"))
    turn_sample_path = write_topic_turn_samples(output_root, records)
    artifacts.append(artifact_entry(output_root, turn_sample_path, len(TOPICS) * 3, "application/x-ndjson"))

    distributions = {
        "split": dict(sorted(Counter(r["split"] for r in records).items())),
        "topic": dict(sorted(Counter(r["topic"] for r in records).items())),
        "formality": dict(sorted(Counter(r["formality"] for r in records).items())),
        "turn_count": {str(k): v for k, v in sorted(Counter(r["turn_count"] for r in records).items())},
    }
    manifest = {
        "dataset": "turkish-daily-dialogues-5k",
        "version": DATASET_VERSION,
        "generated_with": {
            "script": "scripts/generate_dataset.py",
            "generator_version": GENERATOR_VERSION,
            "seed": SEED,
            "network_required": False,
            "runtime_model_inference": False,
            "ai_assisted_authoring": True,
        },
        "record_count": len(records),
        "topic_count": len(TOPICS),
        "split_strategy": {
            "unit": "scenario_family",
            "families_per_topic": SCENARIO_FAMILIES_PER_TOPIC,
            "train_families_per_topic": TRAIN_FAMILIES_PER_TOPIC,
            "validation_families_per_topic": VALIDATION_FAMILIES_PER_TOPIC,
            "test_families_per_topic": TEST_FAMILIES_PER_TOPIC,
        },
        "distributions": distributions,
        "artifacts": sorted(artifacts, key=lambda item: item["path"]),
    }
    manifest_path = output_root / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checksum_paths = [output_root / entry["path"] for entry in manifest["artifacts"]] + [manifest_path]
    checksum_lines = [f"{sha256(path)}  {path.relative_to(output_root).as_posix()}" for path in checksum_paths]
    (output_root / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=("jsonl", "parquet"),
        default=("jsonl", "parquet"),
        help="Release formats to generate (default: jsonl parquet)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(args.output_root.resolve(), tuple(args.formats))
