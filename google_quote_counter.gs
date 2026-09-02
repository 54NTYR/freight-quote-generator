/**
 * Paste into Extensions > Apps Script on the quote-counter Sheet.
 * Replace PASTE_THE_SAME_PASSWORD_HERE with the same password saved in Settings.
 * After edits: Deploy > Manage deployments > pencil > New version.
 * The number lives in A2 of the first tab that is not named Log.
 */

const SECRET = "PASTE_THE_SAME_PASSWORD_HERE";
const LOG_SHEET = "Log";

function doGet(e) {
  return handle_(e && e.parameter);
}

function doPost(e) {
  return handle_(e && e.parameter);
}

function handle_(params) {
  params = params || {};
  if (params.action === "next") {
    return nextNumber_(params.secret, params.mode);
  }
  return json_({ ok: true, quote_number: currentNumber_() });
}

function nextNumber_(secret, mode) {
  if (String(secret || "") !== SECRET) {
    return json_({ ok: false, error: "bad_secret" });
  }
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const sheet = counterSheet_();
    const cell = sheet.getRange("A2");
    const next = Number(cell.getValue() || 0) + 1;
    cell.setValue(next);
    sheet.getRange("B2").setValue(new Date());
    logSheet_().appendRow([new Date(), next, String(mode || "")]);
    SpreadsheetApp.flush();
    return json_({ ok: true, quote_number: next });
  } finally {
    lock.releaseLock();
  }
}

function currentNumber_() {
  return Number(counterSheet_().getRange("A2").getValue() || 0);
}

function counterSheet_() {
  const sheets = SpreadsheetApp.getActive().getSheets();
  for (var i = 0; i < sheets.length; i++) {
    if (sheets[i].getName() !== LOG_SHEET) {
      return sheets[i];
    }
  }
  return sheets[0];
}

function logSheet_() {
  const ss = SpreadsheetApp.getActive();
  var sheet = ss.getSheetByName(LOG_SHEET);
  if (!sheet) {
    sheet = ss.insertSheet(LOG_SHEET, ss.getNumSheets());
    sheet.getRange("A1:C1").setValues([["When", "QuoteNumber", "Mode"]]);
  }
  return sheet;
}

function json_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
