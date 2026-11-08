# KIVORA – video katalog a přehrávač pro Kodi

KIVORA je neoficiální komunitní doplněk Kodi s vyhledáváním Webshare, metadaty filmů, plakáty a katalogem filmů i seriálů.

**Technické ID zůstává `plugin.video.fckyo`:** KIVORA je nový zobrazovaný název původního doplňku FCKYO. Verze KIVORA 0.47.0 a repozitář 1.0.1 upravují i název přímo v instalačních metadatech Kodi. Historie přehrávání, účet i nastavení této instalace zůstávají zachované. Starší samostatný doplněk `plugin.video.yawsp` není touto aktualizací dotčen.

## Struktura repozitáře

Hlavní větev obsahuje pouze soubory potřebné pro **Kodi KIVORA**, jeho testování a vydávání aktualizací:

- `plugin.video.fckyo/` – samotný Kodi doplněk, včetně modulů, lokalizací, skinů a licence. Technické ID zůstává kvůli kompatibilitě.
- `tests/` – regresní testy pro přehrávání, televizní rozhraní, katalog a vyhledávání. Některé testy záměrně ověřují i starší kompatibilní obrazovku.
- `tools/` – nástroje pro generování grafiky a audit sestavení.
- `build_repo.py` – generátor Kodi repozitáře a instalačních ZIPů.
- `.github/workflows/publish-kivora.yml` – testy a publikování GitHub Pages.
- `.github/workflows/cinema-100-full.yml` – volitelný rozšířený audit.

**Samostatná Windows/Electron aplikace neslouží k běhu Kodi.** Její původní zdrojové soubory a sestavovací workflow zůstávají dostupné v archivní větvi [archive/standalone-desktop-20261102](https://github.com/sugarekv-cloud/bozsky-prehravac/tree/archive/standalone-desktop-20261102). Na hlavní větvi byly odstraněny také duplicitní importní archiv `desktop-source.b64` a zastaralý workflow pro návrhovou větev Cinema 0.36.

## Instalace přes repozitář

GitHub Pages: https://sugarekv-cloud.github.io/bozsky-prehravac/

**Pozor:** Samotný ZIP repozitáře není ZIP aplikace. Nejprve instalujte repozitář, potom KIVORA z něj. Kodi musí být na televizoru nebo připojeném Android TV boxu / Fire TV; běžný systém některých televizorů Kodi nepodporuje.

1. Stáhněte [instalační ZIP repozitáře](https://sugarekv-cloud.github.io/bozsky-prehravac/repository.bozskyprehravac-1.0.1.zip). Nerozbalujte jej.
2. ZIP přeneste do TV přes USB, sdílenou složku nebo jej stáhněte přímo v Android TV. V Kodi otevřete **Nastavení → Systém → Doplňky** a případně povolte **Neznámé zdroje**.
3. Na televizoru zvolte **Doplňky → Instalovat ze souboru ZIP** a otevřete instalační ZIP repozitáře.
4. Otevřete **Doplňky → Instalovat z repozitáře → KIVORA repozitář → Video doplňky → KIVORA → Instalovat**.
5. Spusťte **KIVORA** a v ozubeném kolečku nastavte účet Webshare.

ID repozitáře zůstává `repository.bozskyprehravac`, aby jeho dosavadní instalace fungovaly dál. Stejná je také URL GitHub Pages; mění se pouze zobrazované názvy a verze repozitáře. Pokud Kodi ještě zobrazuje původní název repozitáře, jde o staré pojmenování stejného zdroje.

**Aktualizace z FCKYO na KIVORA:** Neodinstalovávejte původní `plugin.video.fckyo`. Ve správci doplňků zvolte Aktualizovat / Verze a vyberte KIVORA repozitář. Zachováte tak lokální data. Pokud vidíte starý název, Kodi může mít starou verzi metadat; proveďte kontrolu aktualizací a restart.

## Katalog a aktualizace

Kodi na zařízení průběžně načítá katalogová metadata Cinemeta a vyhledává skutečné dostupné soubory na Webshare. Dostupnost musí být před zobrazením filmu ověřená; sama filmová databáze žádná videa neposkytuje. V rozhraní lze pod ozubeným kolečkem zvolit další synchronizační dávku. Veřejná data nemusejí obsahovat všechny existující filmy; není to nepřetržitý background indexer.

Změna čísla verze v `plugin.video.fckyo/addon.xml` spustí pomocí GitHub Actions nové sestavení repozitáře. Testy: `python -m unittest discover -s tests -v`. Vygenerování balíčku: `python build_repo.py --owner sugarekv-cloud --output site`.

## Licence a původ projektu

Zdrojový kód tohoto Kodi doplňku zahrnuje úpravy staršího svobodného projektu. Autorská historie a povinné informace jsou v `plugin.video.fckyo/CREDITS.md`, původní licence AGPL-3.0 zůstává v `plugin.video.fckyo/LICENSE`. Změna názvu a technického ID neznamená změnu autorství, licence ani vznik nové nezávislé implementace. Nepoužívejte soubory, ke kterým nemáte oprávnění.


### ŽIVÁ TV (od verze 0.47.0)

KIVORA obsahuje samostatnou záložku **ŽIVÁ TV** s několika bezplatně dostupnými českými televizními streamy (Óčko, Óčko Expres, Óčko Star, TV POLAR, Praha TV), zobrazenými přes Kodi HLS přehrávač. Není nutný účet Webshare. Na kartě stiskněte **OK** pro živé přehrávání; tlačítko kontextové nabídky přidá nebo odebere stanici z místních oblíbených. Po zastavení přehrávání se KIVORA vrátí do TV přehledu.

Pro živou Českou televizi a archiv slouží položka **ČESKÁ TELEVIZE · iVysílání**, která otevírá samostatný doplněk Kodi `plugin.video.ivysilani.cz`, pokud už je instalován. KIVORA automaticky neinstaluje ani nepřepisuje jiné doplňky.

Streamy mohou časem změnit adresy nebo dostupnost; některé mohou být geograficky omezené. První verze nemá vlastní EPG a neumožňuje sledování placených televizí bez oprávnění.


### Připravená verze 0.47.4 – čitelnost a seriály

Navazuje na 0.47.2 a zachovává technické ID, Webshare, popisy z ČSFD,
živou TV, profily, oblíbené a historii. Horní nabídka má větší horní odstup;
nápověda je mimo tlačítka a názvy karet, rok a kvalita mají samostatné místo.
Výběr má bílý rámeček po všech stranách a hlavní tlačítko červené zvýraznění.
Série i epizody přebírají obrázky a popis seriálu, epizody se řadí číselně
a stejný ident Webshare se nepočítá jako více verzí. Výběr souboru epizody
ponechává aktivní záložku Seriály.

Filtr explicitního obsahu je zapojen také do hledání jednotlivých souborů
a jejich výpisu; zachovává příznaky adult z metadat. Kontroluje příznaky,
kategorii a silné signály v názvu, nikoli sexuální témata v synopsi.
Neoznačený obsah s neutrálním názvem nelze tímto filtrem spolehlivě rozpoznat.

Ověření: 382 automatických testů, kompilace Pythonu a sestavení repozitáře.
Před vydáním zbývá kontrola v Kodi na TV: horní menu a dlouhé české názvy,
pohyb mezi kartami a tlačítky, návrat epizoda → soubory → přehrávání → epizody,
zobrazení ČSFD popisu a obnova vygenerovaných textur po aktualizaci.
