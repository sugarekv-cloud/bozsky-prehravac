# Božský přehrávač pro Kodi

Komunitní video doplněk Kodi založený na YAWsP, licence AGPL-3.0.
Technické ID doplňku zůstává `plugin.video.yawsp`.
Filmografická metadata jsou pomocná; katalog zobrazuje pouze videa
ověřená přes uživatelovo připojení k Webshare.

## Instalace přes repozitář (doporučeno)

**Stránka komunitního repozitáře:**
https://sugarekv-cloud.github.io/bozsky-prehravac/

1. Stáhněte ZIP repozitáře:
   https://sugarekv-cloud.github.io/bozsky-prehravac/repository.bozskyprehravac-1.0.0.zip
   (archiv nerozbalujte).
2. Otevřete Kodi → **Nastavení (ozubené kolečko) → Systém → Doplňky**.
   Pro instalaci neoficiálního ZIPu povolte **Neznámé zdroje**.
3. Kodi → **Doplňky → Instalovat ze souboru ZIP**. Vyberte právě
   stažený `repository.bozskyprehravac-1.0.0.zip`.
   Na televizoru lze ZIP zkopírovat přes USB nebo síťový disk.
4. Kodi → **Doplňky → Instalovat z repozitáře → Božský repozitář →
   Video doplňky → Božský přehrávač → Instalovat**.
5. Otevřete Božský přehrávač. Ozubené kolečko v pravém horním rohu
   nabízí přihlášení Webshare, filtry a ruční aktualizaci katalogu.

Pokud je doplněk již instalován *ručně z jeho vlastního ZIPu*:
neodinstalovávejte jej ani nemažte data. Otevřete **Moje doplňky →
Video doplňky → Božský přehrávač → Verze / Aktualizovat** a pokud
je v nabídce, vyberte verzi z **Božského repozitáře**.
V nastavení Kodi je možné zvolit automatické aktualizace a
v prohlížeči doplňků spustit **Zkontrolovat aktualizace**.

## Katalog a synchronizace

Cinemeta (veřejná katalogová metadata, bez API klíče) poskytuje názvy,
roky, plakáty a případně hodnocení IMDb. Volitelná CZDB/ČSFD metadata
jsou preferována pro české názvy a hodnocení. Cinemeta je *seznam
kandidátů*, nikoliv důkaz dostupnosti na Webshare. Kodi při otevření
postupně prověřuje omezený počet titulů přes Webshare API a ukládá
index na zařízení. Ozubené kolečko → **Načíst další tituly a
aktualizovat Webshare** spustí další dávku. Režim není trvalá
synchronizační služba spuštěná na pozadí.

Použité zdroje:
- https://cinemeta-catalogs.strem.io/top/catalog/movie/top.json
- https://v3-cinemeta.strem.io/manifest.json

Přítomnost filmu v katalogu neznamená, že je soubor trvale dostupný.
Jazykové označení v názvu souboru není záruka dabingu.

## Údržba a automatické aktualizace

GitHub Actions při změně větve `main` spouští testy, generují
`addons.xml`, `addons.xml.md5` a instalační ZIP doplňku.
GitHub Pages následně nabízí Kodi nové verze přes repozitář.
Vydávání se řídí verzí z `plugin.video.yawsp/addon.xml`.

Testy: `python -m unittest discover -s tests -v`.
Sestavení: `python build_repo.py --owner sugarekv-cloud --output site`.

Katalogový kód nedistribuuje filmy a nepoužívá heslo Webshare při
stahování veřejných metadat. Používejte pouze obsah, k němuž máte oprávnění.
