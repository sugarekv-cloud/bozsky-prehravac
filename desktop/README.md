# Božský přehrávač 2.0 — Desktop Alpha

Samostatný filmový katalog a přehrávač pro **Windows**, bez závislosti na Kodi. Moderní televizní rozhraní, Webshare jako zdroj dostupnosti a metadata z Cinemeta (volitelně české překlady z TMDb s vlastním API klíčem).

## Spuštění vývojové verze

1. Nainstaluj **Node.js 22+**.
2. V této složce spusť `npm install`.
3. Spusť `npm test` a `npm start`.
4. V aplikaci vyber **Připojit Webshare** a přihlas se. Přihlašovací údaje se neposílají žádnému námi provozovanému serveru.
5. Pro podporu MKV/HEVC doporučujeme nainstalovat přehrávač **mpv** a vybrat cestu k `mpv.exe` v nastavení aplikace.

## Sestavení Windows instalátoru

`npm run package:win` — vytvoří instalátor i přenosnou aplikaci v `release/`.

GitHub Actions `.github/workflows/desktop-windows.yml` sestavuje Windows soubory automaticky ze složky `desktop/` repozitáře.

## Co už alfa verze obsahuje

- Webshare přihlášení přes veřejné API (`salt` + md5crypt + SHA1), lokální šifrované uložení tokenu, nikdy neukládá heslo.
- Vyhledávání a seskupování skutečně dostupných videosouborů, kontrola `file_exists` a `downloadable`.
- Filmy, seriály, seřazení sérií a epizod, ruční výběr kvality.
- Katalogová data přes Cinemeta; čeština přes **volitelný** vlastní TMDb API klíč.
- Vlastní tmavý TV design, dálkové ovládání klávesami, filtrování kvality/CZ, oblíbené a historie sledování.
- Přehrání podporovaných formátů přímo; volitelně externí mpv pro MKV, HEVC, pokročilé audio/subtitle formáty.
- Offline lokální preference a lokální mezipaměť pouze po dobu běhu.

## Omezení této první alfy

- Živý Webshare účet a odehrání skutečného souboru nebyly v prostředí tvůrce end-to-end otestovány.
- Veřejný Webshare API neposkytuje úplný filmový katalog ani zaručené jazykové stopy; vyhledávání a štítky CZ se odvozují z názvu.
- Některé filmy nemají poster nebo metadata. ČSFD nemá veřejné oficiální API poskytované pro tento projekt; proto jej neužíváme neautorizovaným scrapováním.
- Android TV/APK a samoaktualizace zatím **nejsou dokončené**. Toto vydání je Windows alpha.
- Externí mpv musí být nainstalované samostatně. Pozice sledování v externím mpv se zatím nesynchronizuje automaticky.
- Instalátor zatím není digitálně podepsaný, Windows může zobrazit SmartScreen.

## Bezpečnost a legální použití

Aplikace pouze vyhledává skutečně dostupné soubory přes Webshare. Používej ji jen na obsah, ke kterému máš práva. Nepřipojuje se k serveru tvůrce. Přístupové údaje a tokeny nikdy nepublikuj v repozitáři. Přihlašovací token se uloží pouze tehdy, když Electron nabízí systémové šifrované úložiště.
