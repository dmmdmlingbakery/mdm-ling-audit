import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import pytz
import re

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"

# --- APP LAYOUT ---
st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍", layout="wide")

st.title("🍍 Mdm Ling Bakery Stock Audit")

# Button to trigger the check
if st.button("RUN FULL AUDIT", type="primary"):
    
    with st.spinner("Fetching live data..."):
        try:
            # 1. Add Headers to mimic a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(FEED_URL, headers=headers)
            response.raise_for_status() 
            
            # 2. Parse the XML
            xml_content = response.text
            
            # Remove namespaces to avoid parsing errors
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)
            
            root = ET.fromstring(xml_content)
            
            all_items = []
            
            # 3. Find 'item' ANYWHERE in the file
            items = root.findall('.//item')
            
            if not items:
                st.error("No items found. Server response:")
                st.code(response.text[:500])
            
            for item in items:
                # Find Title
                title = item.find('title')
                if title is None: 
                    continue
                title_text = title.text

                # Find Availability
                avail_text = None
                for child in item:
                    if 'availability' in child.tag:
                        avail_text = child.text
                        break
                
                if title_text is None or avail_text is None:
                    continue
                
                # Clean Name
                clean_name = title_text.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                
                # Determine Status & Sort Order
                # 0 = Out of Stock (Top), 1 = In Stock (Bottom)
                if avail_text == 'out_of_stock':
                    status_display = "🔴 Out of Stock"
                    sort_key = 0 
                else:
