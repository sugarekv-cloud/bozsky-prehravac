# YAWsP Smart Search 0.4.0 – Novinky / SCC-style browser

This is a third-party modified fork of YAWsP 0.2.0 with changes introduced in 0.3.0. AGPL-3.0 license retained. It keeps the original add-on ID `plugin.video.yawsp` and therefore **replaces** an installed YAWsP version (back up settings and the old addon first). Target is Kodi 19+ (Python 3). No account credentials are included.

## Functionality

- **Novinky**: newly indexed/uploaded Webshare **video files**, ordered using the documented Webshare search `sort=recent` option. Submenus: films, episodes, TV series with new files, all files, filename-year selection, quality/audio/HDR settings.
- Filename heuristics detect movie titles, year markers, TV episode markers (`S01E02`, `1x02`), season packs, and common resolution/HDR and Czech/dual language **labels**.
- Multiple file variants of a title or episode are grouped in a single Kodi catalog card (within the returned Webshare results page). When a title is opened, Webshare is queried again for the title and its matching files are listed, quality-first. **No autoplay.** Click a file to use the original YAWsP `play` action via its Webshare `ident`.
- Filters: minimal quality (all/720p/1080p/4K), only files with presumed CZ audio in the name, only files marked HDR, filename year. Pagination is based on pages of 100 *original* Webshare search results; filtered pages can be sparse/empty. Some variants of the same title may occur on different pages.
- Original YAWsP Smart Search, queue, history, download, login and search entry points remain unchanged.

## Caveats

- **Not an authoritative movie catalogue.** `recent` means recent files on Webshare, **not** recently released movies or aired episodes. The year is extracted from the filename, and may be missing or misleading. No movie premiere dates, true ratings, genre data, curated posters, recent-airing notifications, or recommender are provided. Film vs. TV classification is heuristic and may be wrong, especially for poorly named files.
- Filenames alone do **not** verify video resolution, HDR mastering or audio language. `CZ*` and `HDR*` mean hints from filenames, not verified technical properties. Files named only with `CZsub` / `CZ.SUBS` are **not** considered explicitly dubbed.
- The public Webshare search API may change or fail, searches may be limited to a page, and files may disappear. It has not been live-tested against a Webshare account or tested on a real Kodi installation in this environment. Unit tests used simulated Webshare API XML and Kodi interfaces.
- Existing ČSFD lookup (0.3.0) relies on unofficial HTML parsing and may stop working. These New Releases menus do not use ČSFD for metadata; they use Webshare filenames only. This is **not** Stream Cinema Community, only a menu/browsing design inspired by some of its functionality.

## Install

1. Back up the original `plugin.video.yawsp` add-on and Kodi user settings.
2. Kodi → Settings → Add-ons → Install from ZIP file → `plugin.video.yawsp-0.4.0-novinky-scc.zip`.
3. In YAWsP settings, configure your own Webshare credentials if necessary.
4. Open **YAWsP → NOVINKY**. Select a catalogue and then a title to view variants; choose a variant manually to play.
5. To disable the release filters, enter **Novinky → Filtry kvality/jazyka/HDR**.

Webshare API documentation: https://webshare.cz/apidoc/ (search, sorted by `recent`).
