// PP_GITHUB_RELEASE_OTA_V1
// Loaded last by gas-deploy.yml (sorted *.gs) to override legacy Drive OTA discovery.

function ppOtaGithubMetaLine_(body, key) {
  const prefix = String(key || '') + '=';
  const lines = String(body || '').split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].indexOf(prefix) === 0) return lines[i].slice(prefix.length).trim();
  }
  return '';
}

function ppOtaGithubReleases_() {
  const cache = CacheService.getScriptCache();
  const key = 'PP_GITHUB_RELEASES_OTA_V1';
  const cached = cache.get(key);
  if (cached) {
    try { return JSON.parse(cached); } catch (_) {}
  }
  const response = UrlFetchApp.fetch(PP.RELEASES, {
    muteHttpExceptions: true,
    headers: {
      'Accept': 'application/vnd.github+json',
      'User-Agent': 'pick-pack-1291-ota'
    }
  });
  if (response.getResponseCode() !== 200) throw new Error('GITHUB_RELEASES_HTTP_' + response.getResponseCode());
  const releases = JSON.parse(response.getContentText() || '[]');
  cache.put(key, JSON.stringify(releases), 60);
  return releases;
}

function ppUpdateCheck_(body) {
  const channel = ppFold_(body.channel || body._app_channel) === 'STABLE' ? 'STABLE' : 'BETA';
  const current = String(body.current_version || body._app_version || '').trim();
  const releases = ppOtaGithubReleases_();
  let best = null;

  releases.forEach(function(rel) {
    if (!rel || rel.draft) return;
    const meta = String(rel.body || '');
    if (ppFold_(ppOtaGithubMetaLine_(meta, 'PP_CHANNEL')) !== channel) return;
    const version = ppOtaGithubMetaLine_(meta, 'PP_VERSION');
    const apkName = ppOtaGithubMetaLine_(meta, 'PP_APK_NAME');
    if (!version || !apkName) return;
    const assets = Array.isArray(rel.assets) ? rel.assets : [];
    const asset = assets.find(function(a) { return String(a && a.name || '') === apkName; });
    if (!asset || !asset.browser_download_url) return;
    if (!best || ppOtaCompare_(version, best.version) > 0) best = {rel: rel, asset: asset, version: version, meta: meta};
  });

  if (!best) return {ok:true, source:'GITHUB_RELEASE', channel:channel, available:false, reason:'NO_RELEASE'};

  const available = ppOtaCompare_(best.version, current) > 0;
  const out = {
    ok: true,
    source: 'GITHUB_RELEASE',
    channel: channel,
    available: available,
    version_name: best.version,
    version_code: Number(ppOtaGithubMetaLine_(best.meta, 'PP_VERSION_CODE') || 0),
    size: Number(ppOtaGithubMetaLine_(best.meta, 'PP_SIZE') || best.asset.size || 0),
    published_at: String(best.rel.published_at || best.rel.created_at || ''),
    notes: String(best.rel.name || ('Pick Pack 1291 ' + best.version)),
    mandatory: ppFold_(ppOtaGithubMetaLine_(best.meta, 'PP_MANDATORY')) === 'TRUE'
  };
  if (!available) return out;

  out.sha256 = String(ppOtaGithubMetaLine_(best.meta, 'PP_SHA256') || '').toLowerCase();
  out.apk_url = String(best.asset.browser_download_url || '');
  if (!/^[0-9a-f]{64}$/.test(out.sha256) || !/^https:\/\/github\.com\//.test(out.apk_url)) {
    return {ok:false, error:'OTA_GITHUB_METADATA_INVALID', source:'GITHUB_RELEASE', channel:channel};
  }
  return out;
}
