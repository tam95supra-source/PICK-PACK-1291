const PP_SPREADSHEET_ID = '1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78';
const PP_SECRET_PROPERTY = 'PP_SHEET_WEBHOOK_SECRET';
const PP_EVENT_METADATA_KEY = 'PP_EVENT_ID';
const PP_SEQ_METADATA_KEY = 'PP_SERVER_SEQ';
const PP_MAX_EVENTS = 100;
const PP_ALLOWED_SHEETS = Object.freeze({
  'RA - VÀO TRONG CA': true,
  'CÔNG NHẬT': true,
});

function doGet() {
  return ppJson_({
    ok: true,
    service: 'pick-pack-1291-sheet-projection',
    mode: 'write-only-webhook',
  });
}

function doPost(e) {
  try {
    const body = ppParseBody_(e);
    if (body.mode !== 'pp_projection') return ppJson_({ ok: false, error: 'MODE_NOT_ALLOWED' });

    const configuredSecret = PropertiesService.getScriptProperties().getProperty(PP_SECRET_PROPERTY) || '';
    if (!configuredSecret || !ppConstantTimeEqual_(String(body.secret || ''), configuredSecret)) {
      return ppJson_({ ok: false, error: 'UNAUTHORIZED' });
    }

    const events = Array.isArray(body.events) ? body.events : [];
    if (events.length < 1 || events.length > PP_MAX_EVENTS) {
      return ppJson_({ ok: false, error: 'EVENT_COUNT_INVALID' });
    }

    const lock = LockService.getScriptLock();
    lock.waitLock(25000);
    try {
      const spreadsheet = SpreadsheetApp.openById(PP_SPREADSHEET_ID);
      const ackEventIds = [];
      const ordered = events.slice().sort(ppCompareEvents_);

      ordered.forEach(function (event) {
        ppValidateEvent_(event);
        ppUpsertProjectionRow_(spreadsheet, event);
        ackEventIds.push(String(event.event_id));
      });

      SpreadsheetApp.flush();
      return ppJson_({ ok: true, ack_event_ids: ackEventIds });
    } finally {
      lock.releaseLock();
    }
  } catch (error) {
    return ppJson_({ ok: false, error: ppSafeError_(error) });
  }
}

function ppUpsertProjectionRow_(spreadsheet, event) {
  const eventId = String(event.event_id);
  const sheetName = String(event.sheet_name);
  const sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) throw new Error('SHEET_NOT_FOUND:' + sheetName);

  const headers = ppHeaders_(sheet);
  const rowData = event.row_data || {};
  const unknownKeys = Object.keys(rowData).filter(function (key) { return headers.indexOf(key) < 0; });
  if (unknownKeys.length) throw new Error('UNKNOWN_HEADERS:' + unknownKeys.join(','));

  const values = headers.map(function (header) {
    return ppLiteralCell_(Object.prototype.hasOwnProperty.call(rowData, header) ? rowData[header] : '');
  });

  const existing = spreadsheet
    .createDeveloperMetadataFinder()
    .withKey(PP_EVENT_METADATA_KEY)
    .withValue(eventId)
    .withLocationType(SpreadsheetApp.DeveloperMetadataLocationType.ROW)
    .withVisibility(SpreadsheetApp.DeveloperMetadataVisibility.PROJECT)
    .find();

  let rowNumber;
  if (existing.length > 1) throw new Error('DUPLICATE_EVENT_METADATA:' + eventId);

  if (existing.length === 1) {
    const rowRange = existing[0].getLocation().getRow();
    if (!rowRange) throw new Error('EVENT_METADATA_LOCATION_INVALID:' + eventId);
    if (rowRange.getSheet().getName() !== sheetName) throw new Error('EVENT_SHEET_MISMATCH:' + eventId);
    rowNumber = rowRange.getRow();
  } else {
    rowNumber = Math.max(sheet.getLastRow() + 1, 2);
    const wholeRow = sheet.getRange(rowNumber + ':' + rowNumber);
    wholeRow.addDeveloperMetadata(
      PP_EVENT_METADATA_KEY,
      eventId,
      SpreadsheetApp.DeveloperMetadataVisibility.PROJECT
    );
    if (event.server_seq !== null && event.server_seq !== undefined) {
      wholeRow.addDeveloperMetadata(
        PP_SEQ_METADATA_KEY,
        String(event.server_seq),
        SpreadsheetApp.DeveloperMetadataVisibility.PROJECT
      );
    }
  }

  // Metadata is reserved before values are written. If execution stops between these
  // two operations, a retry finds the same row and completes it instead of appending a duplicate.
  sheet.getRange(rowNumber, 1, 1, headers.length).setValues([values]);
}

function ppHeaders_(sheet) {
  const lastColumn = sheet.getLastColumn();
  if (lastColumn < 1) throw new Error('HEADER_ROW_EMPTY:' + sheet.getName());
  const headers = sheet.getRange(1, 1, 1, lastColumn).getDisplayValues()[0].map(function (v) {
    return String(v || '').trim();
  });
  while (headers.length && headers[headers.length - 1] === '') headers.pop();
  if (!headers.length || headers.some(function (v) { return !v; })) {
    throw new Error('HEADER_CONTRACT_INVALID:' + sheet.getName());
  }
  if (new Set(headers).size !== headers.length) throw new Error('HEADER_DUPLICATE:' + sheet.getName());
  return headers;
}

function ppValidateEvent_(event) {
  if (!event || typeof event !== 'object') throw new Error('EVENT_INVALID');
  const eventId = String(event.event_id || '');
  if (!/^[0-9a-fA-F-]{36}$/.test(eventId)) throw new Error('EVENT_ID_INVALID');
  const sheetName = String(event.sheet_name || '');
  if (!PP_ALLOWED_SHEETS[sheetName]) throw new Error('SHEET_NOT_ALLOWED:' + sheetName);
  if (!event.row_data || typeof event.row_data !== 'object' || Array.isArray(event.row_data)) {
    throw new Error('ROW_DATA_INVALID:' + eventId);
  }
}

function ppParseBody_(e) {
  const raw = e && e.postData && e.postData.contents ? e.postData.contents : '';
  if (!raw || raw.length > 1024 * 1024) throw new Error('BODY_INVALID');
  const body = JSON.parse(raw);
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('BODY_INVALID');
  return body;
}

function ppCompareEvents_(a, b) {
  const aSeq = Number(a && a.server_seq);
  const bSeq = Number(b && b.server_seq);
  if (Number.isFinite(aSeq) && Number.isFinite(bSeq) && aSeq !== bSeq) return aSeq - bSeq;
  return String(a && a.event_id || '').localeCompare(String(b && b.event_id || ''));
}

function ppLiteralCell_(value) {
  if (value === null || value === undefined) return '';
  const text = String(value);
  // Prevent untrusted sheet-derived or user-derived text from becoming a formula.
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

function ppConstantTimeEqual_(left, right) {
  left = String(left || '');
  right = String(right || '');
  const length = Math.max(left.length, right.length);
  let diff = left.length ^ right.length;
  for (let i = 0; i < length; i++) {
    diff |= (left.charCodeAt(i % Math.max(left.length, 1)) || 0) ^
      (right.charCodeAt(i % Math.max(right.length, 1)) || 0);
  }
  return diff === 0;
}

function ppSafeError_(error) {
  const message = error && error.message ? String(error.message) : String(error || 'UNKNOWN');
  return message.replace(/[\r\n\t]+/g, ' ').slice(0, 300);
}

function ppJson_(value) {
  return ContentService
    .createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
