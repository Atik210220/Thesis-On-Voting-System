
Integrated tamper monitor with email alerts.

- SMTP placeholders were added to settings.py (EMAIL_HOST_USER, EMAIL_HOST_PASSWORD).
- tamper_monitor.py monitors 'votes' table using binlog and sends emails to voters of running elections.
- root MySQL is assumed to have no password (passwd set to '').

To use:
1) Generate a Gmail App Password and put it in settings.py as EMAIL_HOST_PASSWORD.
2) Ensure MariaDB binlog is enabled and binlog_format=ROW.
3) Activate your virtualenv and install requirements: pip install pymysql mysql-replication
4) Run Django: python manage.py runserver
