# tamper_monitor.py
import threading
import time
import traceback
from django.conf import settings
from django.utils import timezone
from django.db import connection

# binlog reader
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import UpdateRowsEvent, DeleteRowsEvent

# local email helper (fallback)
from .email_alert import send_email_smtp_direct

# ================= CONFIG =================
MYSQL_CONN = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "passwd": "",   # you said root has no password
}
SERVER_ID = 9999            # pick unique id
DB_NAME = "votingdb"        # change if your DB name is different
TABLE_NAME = "votes"
# ==========================================

def get_running_voter_emails():
    """
    Get distinct emails of voters who are registered (is_approved=1)
    for elections whose status is 'running'.
    """
    emails = set()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT v.email
                FROM election_voters ev
                JOIN voters v ON ev.voter_id = v.voter_id
                JOIN elections e ON ev.election_id = e.election_id
                WHERE e.status = 'running' AND ev.is_approved = 1
            """)
            rows = cursor.fetchall()
            for r in rows:
                if r and r[0]:
                    emails.add(r[0])
    except Exception as e:
        print("Error fetching running voter emails:", e)
    return list(emails)


def notify_running_voters(reason_text):
    emails = get_running_voter_emails()
    if not emails:
        print("No running-election voter emails found to notify.")
        return

    subject = "⚠️ Tampering Alert in Voting System"
    message = f"Dear voter,\n\nA possible vote tampering has been detected in a running election.\n\nDetails: {reason_text}\n\nPlease contact the administrator immediately.\n\n— Online Voting System Security"

    # Prefer Django send_mail (if configured), but prefer our direct SMTP fallback for reliability
    try:
        # Try Django's send_mail first for consistency with settings
        from django.core.mail import send_mail
        sent_count = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, emails, fail_silently=False)
        print(f"✅ Django send_mail returned {sent_count} for {len(emails)} recipients.")
    except Exception as e:
        print("Django send_mail failed, falling back to direct SMTP. Error:", e)

        ok, info = send_email_smtp_direct(emails, subject, message)
        if ok:
            for em in emails:
                print(f"✅ Alert sent to {em} (fallback SMTP)")
        else:
            print("❌ Fallback SMTP failed:", info)


def monitor():
    """
    Main loop — listen to binlog and detect UPDATE/DELETE on votes.
    """
    print("🔒 Tamper detection started... Monitoring votes table")
    while True:
        try:
            stream = BinLogStreamReader(
                connection_settings=MYSQL_CONN,
                server_id=SERVER_ID,
                blocking=True,
                resume_stream=True,
                only_events=[UpdateRowsEvent, DeleteRowsEvent],
                only_schemas=[DB_NAME],
                only_tables=[TABLE_NAME],
            )

            for binlog_event in stream:
                # binlog_event.schema, binlog_event.table available
                for row in binlog_event.rows:
                    # row structure differs for UpdateRowsEvent vs DeleteRowsEvent
                    if isinstance(binlog_event, UpdateRowsEvent):
                        before = row.get("before_values")
                        after = row.get("after_values")
                        reason = f"UPDATE on {DB_NAME}.{TABLE_NAME} at {timezone.now()}: before={before} after={after}"
                        print("⚠️ Detected UPDATE:", reason)
                        notify_running_voters(reason)
                    elif isinstance(binlog_event, DeleteRowsEvent):
                        values = row.get("values")
                        reason = f"DELETE on {DB_NAME}.{TABLE_NAME} at {timezone.now()}: values={values}"
                        print("⚠️ Detected DELETE:", reason)
                        notify_running_voters(reason)

        except Exception as e:
            print("Tamper monitor exception:", e)
            traceback.print_exc()
            time.sleep(5)  # wait before reconnecting


def start_tamper_monitor():
    t = threading.Thread(target=monitor, daemon=True)
    t.start()
