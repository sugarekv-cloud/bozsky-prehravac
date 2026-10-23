# YAWsP Smart Search 0.3.0

Integrated fork of YAWsP 0.2.0 (AGPL-3.0). This archive is a Kodi add-on with the original id `plugin.video.yawsp`. Install it only if you want to upgrade/replace an existing installation; back up your installation first.

Features: Webshare API search via original login/session; sorted results by title match, resolution (4K, 1080p, 720p), HDR naming, CZ naming. Manually click a result to play it using the original Webshare playback code. The original search/queue/history/download remain.

Limitations: Language/resolution are heuristics based on filename, not validated media metadata. CZ may also mean CZ subtitles. CSFD is unofficial HTML parsing that can break or be blocked. No live Kodi/Webshare tests performed. Only the first 100 results per query (up to four variants) are fetched. This is a development release.

Installation: Kodi > Add-ons > Install from ZIP > select this archive. Kodi must have script.module.requests and script.module.unidecode available. If upgrading, back up settings.
