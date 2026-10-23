# YAWsP Smart Search 0.5.0 – filmový katalog (ČSFD / Webshare)

Neoficiální úprava otevřeného projektu YAWsP, nikoliv vydání původních autorů ani Stream Cinema Community. Licence původního doplňku: AGPL-3.0 (`LICENSE`). Doplněk neobsahuje filmy ani žádné přihlašovací údaje.

## Co je nové

- Karty filmů, seriálů a epizod s českými názvy; plakáty, popisy, žánry, originální názvy a hodnocení, **pokud** je poskytne nezávislá služba CZDB navázaná na ČSFD.
- Samostatné vyhledání filmu v neoficiálním katalogu ČSFD a následné vyhledávání odpovídajících souborů na Webshare.
- Filtry **žánr** a **minimální hodnocení ČSFD**; lze řadit podle nových souborů z Webshare nebo podle skóre ČSFD v načtené stránce.
- Filtry minimálního rozlišení, názvového označení CZ a HDR (jde jen o **značky v názvu**, ne o ověřené zvukové/video stopy).
- Zobrazení různých dostupných kvalit jako variant jednoho titulu na aktuální stránce; po otevření si uživatel vybere konkrétní variantu, přehrávání je **výhradně ruční**.
- Cache metadat se ukládá lokálně do profilu doplňku (`csfd-metadata-cache-v1.json`), pozitivní záznamy 7 dní, negativní 30 minut. Nedostupnost metadat neblokuje procházení Webshare.
- Zůstávají původní funkce YAWsP: přihlášení, vyhledávání, historie, fronta a přehrávání podle ID Webshare.

## Instalace

1. Zálohujte původní addon ID `plugin.video.yawsp`, případně celý profil Kodi a nastavení Webshare.
2. V Kodi 19 nebo novějším otevřete Nastavení → Doplňky → Instalovat ze souboru ZIP.
3. Zvolte `plugin.video.yawsp-0.5.0-csfd-katalog.zip`.
4. Pokud to Kodi vyžaduje, zkontrolujte a případně znovu nastavte vlastní přihlašovací údaje Webshare v nastavení YAWsP.
5. Otevřete položku **KATALOG**. Filtry naleznete pod **ŽÁNRY / HODNOCENÍ / KVALITA / CZ / HDR**.
6. Přepněte zobrazení Kodi na náhledy/plakáty, pokud je podporuje použitý skin.

## Co neznamená „Novinky“

- **Nově přidané** znamená řazení souborů na Webshare přes zdokumentované API `search(sort=recent)`. Nejedná se o data premiér ani o doporučení od ČSFD.
- **Filmy roku 2026** apod. jsou vyhledávány podle roku v názvu souboru; rok lze ověřit katalogem jen u nalezeného záznamu. Nepokrývá to všechny filmové premiéry.
- Katalog se generuje z aktuálních výsledků Webshare (stránky po 100 souborech). Rozličné varianty se sdružují pouze v rámci těchto výsledků, ne globálně přes celý Webshare.
- Žánr/hodnocení se ověřují pouze pro **nejvýše prvních 24** skupin aktuální stránky, aby nedocházelo k nadměrnému zatěžování bezplatného zdroje. Zbylé skupiny nemají na té stránce metadata.
- ČSFD nedisponuje veřejným oficiálním API. Používá se nezávislá služba [CZDB](https://api.czdb.cz/), která je podle autorů určena k nekomerčnímu testování. Nemůžeme garantovat dostupnost, licenční oprávnění k posterům ani úplnost dat.
- Přímé spojení s CZDB (HTTPS s HTTP fallbackem podle jejich dokumentace) není v tomto prostředí živě ověřené; používejte pouze pro osobní účely v souladu s podmínkami poskytovatelů.

## Stav ověření

Syntaktická a XML validace + jednotkové integrační testy simulující Webshare XML a odpovědi katalogu ČSFD; **reálný Kodi, přihlášení Webshare a síťová služba CZDB nebyly v tomto prostředí otestovány**. Pokud metadata z CZDB chybí, procházení souborů funguje bez nich. Pro finální kompatibilitu je potřeba lokální test v Kodi s daným účtem.

Dokumentace API: https://webshare.cz/apidoc/ , https://api.czdb.cz/
