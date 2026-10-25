# KIVORA – video katalog a přehrávač pro Kodi

KIVORA je neoficiální komunitní doplněk Kodi s vyhledáváním Webshare, metadaty filmů, plakáty a katalogem filmů i seriálů.

**Technické ID zůstává `plugin.video.fckyo`:** KIVORA je nový zobrazovaný název původního doplňku FCKYO. Historie přehrávání, účet i nastavení této instalace zůstávají zachované. Starší samostatný doplněk `plugin.video.yawsp` není touto aktualizací dotčen.

## Instalace přes repozitář

GitHub Pages: https://sugarekv-cloud.github.io/bozsky-prehravac/

**Pozor:** Samotný ZIP repozitáře není ZIP aplikace. Nejprve instalujte repozitář, potom KIVORA z něj. Kodi musí být na televizoru nebo připojeném Android TV boxu / Fire TV; běžný systém některých televizorů Kodi nepodporuje.

1. Stáhněte [instalační ZIP repozitáře](https://sugarekv-cloud.github.io/bozsky-prehravac/repository.bozskyprehravac-1.0.0.zip). Nerozbalujte jej.
2. ZIP přeneste do TV přes USB, sdílenou složku nebo jej stáhněte přímo v Android TV. V Kodi otevřete **Nastavení → Systém → Doplňky** a případně povolte **Neznámé zdroje**.
3. Na televizoru zvolte **Doplňky → Instalovat ze souboru ZIP** a otevřete instalační ZIP repozitáře.
4. Otevřete **Doplňky → Instalovat z repozitáře → KIVORA repozitář → Video doplňky → KIVORA → Instalovat**.
5. Spusťte **KIVORA** a v ozubeném kolečku nastavte účet Webshare.

ID repozitáře zůstává `repository.bozskyprehravac`, aby jeho dosavadní instalace fungovaly dál. Stejná je také URL GitHub Pages; mění se pouze ID video doplňku. Pokud Kodi ještě zobrazuje původní název repozitáře, jde o staré pojmenování stejného zdroje.

**Aktualizace z FCKYO na KIVORA:** Neodinstalovávejte původní `plugin.video.fckyo`. Ve správci doplňků zvolte Aktualizovat / Verze a vyberte KIVORA repozitář. Zachováte tak lokální data. Pokud vidíte starý název, Kodi může mít starou verzi metadat; proveďte kontrolu aktualizací a restart.

## Katalog a aktualizace

Kodi na zařízení průběžně načítá katalogová metadata Cinemeta a vyhledává skutečné dostupné soubory na Webshare. Dostupnost musí být před zobrazením filmu ověřená; sama filmová databáze žádná videa neposkytuje. V rozhraní lze pod ozubeným kolečkem zvolit další synchronizační dávku. Veřejná data nemusejí obsahovat všechny existující filmy; není to nepřetržitý background indexer.

Změna čísla verze v `plugin.video.fckyo/addon.xml` spustí pomocí GitHub Actions nové sestavení repozitáře. Testy: `python -m unittest discover -s tests -v`. Vygenerování balíčku: `python build_repo.py --owner sugarekv-cloud --output site`.

## Licence a původ projektu

Zdrojový kód tohoto Kodi doplňku zahrnuje úpravy staršího svobodného projektu. Autorská historie a povinné informace jsou v `plugin.video.fckyo/CREDITS.md`, původní licence AGPL-3.0 zůstává v `plugin.video.fckyo/LICENSE`. Změna názvu a technického ID neznamená změnu autorství, licence ani vznik nové nezávislé implementace. Nepoužívejte soubory, ke kterým nemáte oprávnění.
