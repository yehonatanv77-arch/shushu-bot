"""Dry check: can we read the WhatsApp group size? Prints only the count."""
import sys
sys.path.insert(0, ".")
from whatsapp_poster import group_size
print("GROUP SIZE:", group_size())
