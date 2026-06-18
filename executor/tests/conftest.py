import os

# messaging.py reads MESSAGE_SEPARATOR at import-time → set it before collection.
os.environ.setdefault("MESSAGE_SEPARATOR", "\x1e")
