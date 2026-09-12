"""
Tests package for OfferGet
"""
import os
import sys

# Ensure OfferGet root is in sys.path
OFFERGET_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if OFFERGET_ROOT not in sys.path:
    sys.path.insert(0, OFFERGET_ROOT)
