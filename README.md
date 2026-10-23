# Božský přehrávač – vlastní aktualizace Kodi

Tento projekt obsahuje upravený doplněk YAWsP 0.6.1 a generátor repozitáře Kodi. Jde o neoficiální fork. Licence doplňku: AGPL-3.0, původní autorství zachováno v `addon.xml`.

## Publikace na GitHub Pages

1. Vytvořte na GitHubu **veřejný** repozitář s přesným názvem `bozsky-prehravac`.
2. Nahrajte do něj **obsah tohoto ZIPu** (soubory musí být v kořeni repozitáře, nikoli ve vnořené složce).
3. V GitHub repozitáři otevřete **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Na záložce **Actions** spusťte `Publish Božský repozitář`, pokud se nespustí automaticky.
5. Po úspěšném zveřejnění najdete stránku na `https://VAŠE_JMÉNO.github.io/bozsky-prehravac/`. Odkaz na instalaci repozitáře bude na této stránce.
6. V Kodi nainstalujte ZIP repozitáře, potom otevřete **Instalovat z repozitáře → Božský repozitář → Video doplňky → Božský přehrávač**.

Pozor: neinstalujte ZIP repozitáře před zveřejněním webu; jinak se bude snažit přistupovat k dosud neexistující adrese.

## Aktualizace

Zvyšte číslo `version` v `plugin.video.yawsp/addon.xml` (například `0.6.2`) a upravte kód, commitněte/pushněte na větev `main`. GitHub Actions automaticky přebalí doplněk a aktualizuje `addons.xml` a jeho kontrolní součet. Kodi pak při další kontrole uvidí novou verzi.

Technický identifikátor pluginu je stále `plugin.video.yawsp` z důvodu zachování nastavení, případně může Kodi vyžadovat povolení aktualizací z vybraného repozitáře.

## Test před nasazením

`python3 build_repo.py --owner testuser --output site`

Vygenerovaná testovací URL není skutečně zveřejněná. Živý Kodi, Webshare a katalogová API dosud nebyly integračně ověřeny.
