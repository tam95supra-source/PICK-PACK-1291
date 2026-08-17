// Browser-only authorization helper. Safe to run manually from Apps Script editor.
// It does not send email or mutate operational data; it only touches MailApp so
// Google can request/record the script.send_mail consent for the deploying owner.
function ppAuthorizeMail_() {
  return {ok:true, remaining_daily_quota:MailApp.getRemainingDailyQuota()};
}
