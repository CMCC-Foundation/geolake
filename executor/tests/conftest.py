import os

# messaging.py legge MESSAGE_SEPARATOR a import-time → impostarlo prima della raccolta.
os.environ.setdefault("MESSAGE_SEPARATOR", "\x1e")
