# YAWsP Smart Search 0.6.0 – české filmové premiéry

## Hlavní změna
Sekce **Filmové premiéry ČR** vychází z nezávislého a automaticky aktualizovaného kalendáře českých kinopremiér. Již nejde o řazení Webshare souborů dle uploadu.

Zdroj: https://www.fuxoft.cz/vyplody/premiery/premiery.ics – autor František Fuka, z údajů českých distributorů (UFD). Jde o externí kalendář, nikoli ČSFD API.

- Premiery za posledních 7, 30 a 90 dní
- Premiery během nadcházejících 30 a 90 dní
- Kalendář po měsících (-6 až +18 měsíců)
- Datum uvedení v českém kině, český a původní název, distributor a případně jazyková verze kinokopie
- Volitelné ČSFD/CZDB metadata (plakáty, popis, hodnocení, žánr); selhání metadat neblokuje seznam premiér
- Po otevření titulu ruční vyhledání na Webshare, řazení kvality z názvů, preference označení CZ, nikdy automatické spuštění
- Dřívější `Webshare / nově nahrané soubory` je samostatná položka, včetně seriálů
- Ukládání kalendáře do cache profilu Kodi s TTL 24 h; při nedostupnosti zdroje nejvýše 45 dnů stará cache
- Ruční obnovení kalendáře

### Omezení
Premiéra v kinech **neznamená**, že film existuje jako soubor na Webshare. Datum premiéry kina není rokem výroby filmu. Údaj o dabingu kina není dokladem zvukové stopy Webshare souboru. Zdroj kalendáře může změnit formát, přístupnost nebo termíny. Filmová premiéra je pouze datum pro ČR a není totéž co premiéra seriálu.

### Instalace
Kodi 19+ → Doplňky → Instalovat ze ZIP. Používá ID `plugin.video.yawsp`, může nahradit již nainstalovanou verzi. Zálohujte nastavení. Účet Webshare je vyžadován až při vyhledání videosouboru.

### Testování
Prováděné testy jsou lokální a používají syntetické ICS odpovědi; přímý provoz v Kodi/Webshare a aktuální iCalendar endpoint nebylo možné ověřit v lokálním prostředí bez internetu.
