import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import pytz

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"

# --- APP LAYOUT ---
st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍")

st.title("🍍 Mdm Ling Bakery Stock Audit")
st.write(f"**Target Source:** XML Feed")

# Button to trigger the check
if st.button("RUN AUDIT NOW", type="primary"):
    
    with st.spinner("Fetching live data..."):
        try:
            # 1. Get the Data
            response = requests.get(FEED_URL)
            response.raise_for_status() 
            
            # 2. Parse the XML
            root = ET.fromstring(response.content)
            
            # Define the Google namespace (standard for merchant feeds)
            ns = {'g': 'http://base.google.com/ns/1.0'} 
            
            oos_items = []
            
            # 3. Loop through every product in the feed
            for item in root.findall('channel/item'):
                # --- SAFETY CHECK START ---
                # We fetch the tags first without .text to verify they exist
                title_tag = item.find('title')
                availability_tag = item.find('g:availability', ns)

                # If a product is broken (missing title or availability), SKIP it.
                if title_tag is None or availability_tag is None:
                    continue
                
                # Now it is safe to get the text
                title = title_tag.text
                availability = availability_tag.text
                
                # Check if text is None (empty tags)
                if title is None or availability is None:
                    continue
                # --- SAFETY CHECK END ---
                
                # Clean up the name
                clean_name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                
                # CHECK: Is it explicitly Out of Stock?
                if availability == 'out_of_stock':
                    oos_items.append({
                        "Product Name": clean_name,
                        "Status": "🔴 Out of Stock",
                        "Source": "XML Feed"
                    })

            # 4. Display Results
            sgt_time = datetime.now(pytz.timezone('Asia/Singapore')).strftime("%d %b %Y, %I:%M %p")
            st.success(f"Audit Completed at {sgt_time}")

            if oos_items:
                st.error(f"⚠️ Found {len(oos_items)} Out-of-Stock Items")
                df = pd.DataFrame(oos_items)
                st.dataframe(df, use_container_width=True)
            else:
                st.balloons()
                st.success("✅ Good news! All items in the feed are marked 'In Stock'.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
