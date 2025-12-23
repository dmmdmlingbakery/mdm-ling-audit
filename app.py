import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- WATCHLIST CONFIGURATION ---
# These are the items we MUST deep-check for "Variation Stockouts" (The Range Rule).
WATCHLIST_KEYWORDS = [
    "Premium Pineapple Balls", "Anchor Butter Cookies", "Red Velvet Biscoff",
    "Pink Himalayan", "Kopi Siew Dai", "Molten Chocolate", 
    "Chocolate Coffee", "Green Pea", "Peanut Cookies", 
    "Almond Cookies", "Wholemeal Raisin", "Cranberry Pineapple",
    "Elegance Reunion", "Tote of"
]

# Items to IGNORE (Single variants that are always "one price")
SINGLE_VARIANT_IGNORE = [
    "Pandan", "Kueh Bangkit", "Mixed Berry", "Hojicha", 
    "Nyonya Coconut", "Classic Cheese", "Love Letter"
]

# --- HELPER FUNCTIONS ---

def get_tag_text(item, tag_name_ending):
    """Robustly finds a tag by its name, ignoring the {http...} namespace prefix."""
    for child in item:
        if child.tag.endswith(tag_name_ending) and child.text:
            return child.text
    return None

def check_single_page_range_rule(url: str, product_name: str) -> Dict:
    """Visits a product page to check if the 'Price Range' ($11 - $22) is active."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return {"name": product_name, "status": "⚠️ Link Error", "details": "Could not load page"}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # WooCommerce Price Check
        # We look for the price tag. If multiple variants exist, it usually shows a range.
        price_tag = soup.find(class_='price')
        
        if not price_tag:
             return {"name": product_name, "status": "🟢 In Stock", "details": "No price tag found (Safe)"}

        price_text = price_tag.get_text()
        
        # THE RANGE RULE LOGIC:
        # Hyphen/Dash means "Range" ($11.80 - $22.80) -> All Sizes In Stock
        # No Hyphen means "Single Price" ($22.80) -> One Size (Fun Size) is OOS
        has_range = '–' in price_text or '-' in price_text
        
        if has_range:
            return {"name": product_name, "status": "🟢 In Stock", "details": f"Range verified: {price_text}"}
        else:
            return {
                "name": product_name, 
                "status": "⚠️ Variation OOS", 
                "
