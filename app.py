import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import pytz

# --- CONFIGURATION ---
FEED_URL = "https://www.mdmlingbakery.com/wp-content/uploads/rex-feed/feed-261114.xml"

# --- APP LAYOUT ---
st.set_page_config(page_title="MLB Stock Audit", page_icon="🍍", layout="wide")

st.title("🍍 Mdm Ling Bakery Stock Audit")
st.write(f"**Target Source:** XML Feed")

# Button to trigger the check
if st.button("RUN FULL AUDIT", type="primary"):
    
    with st.spinner("Fetching live data..."):
        try:
            # 1. Get the Data
            response = requests.get(FEED_URL)
            response.raise_for_status() 
            
            # 2. Parse the XML
            root = ET.fromstring(response.content)
            ns = {'g': 'http://base.google.com/ns/1.0'} 
            
            all_items = []
            
            # 3. Loop through every product
            for item in root.findall('channel/item'):
                # Safety Check
                title_tag = item.find('title')
                availability_tag = item.find('g:availability', ns)

                if title_tag is None or availability_tag is None:
                    continue
                
                title = title_tag.text
                availability = availability_tag.text
                
                if title is None or availability is None:
                    continue
                
                # Clean Name
                clean_name = title.replace(" - Mdm Ling Bakery", "").replace("[CNY 2026]", "").strip()
                
                # Determine Status & Sort Order
                # We give OOS a '0' so it sorts to the top, In Stock gets '1'
                if availability == 'out_of_stock':
                    status_display = "🔴 Out of Stock"
                    sort_key = 0 
                else:
                    status_display = "🟢 In Stock"
                    sort_key = 1

                all_items.append({
                    "Product Name": clean_name,
                    "Status": status_display,
                    "sort_key": sort_key # Hidden column for sorting
                })

            # 4. Process Data
            if all_items:
                df = pd.DataFrame(all_items)
                
                # SORT: Put '0' (Out of Stock) at the top
                df = df.sort_values(by=['sort_key', 'Product Name'])
                
                # Drop the hidden sort key so the user doesn't see it
                df = df.drop(columns=['sort_key'])

                # Display Stats
                total_items = len(df)
                oos_count = len(df[df['Status'] == "🔴 Out of Stock"])
                
                sgt_time = datetime.now(pytz.timezone('Asia/Singapore')).strftime("%d %b %Y, %I:%M %p")
                
                # Summary Metrics
                col1, col2 = st.columns(2)
                col1.metric("Total Items Checked", total_items)
                col2.metric("Out of Stock", oos_count, delta_color="inverse")
                
                st.write(f"**Audit Completed:** {sgt_time}")
                
                # Show the full table
                st.dataframe(df, use_container_width=True, hide_index=True)
                
            else:
                st.warning("No items found in the feed.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
