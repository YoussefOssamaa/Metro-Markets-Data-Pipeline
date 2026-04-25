import streamlit as st
import pandas as pd
import plotly.express as px
import json

# --- 1. App Configuration ---
st.set_page_config(page_title="Metro Markets Analytics", layout="wide", page_icon="🛒")

# --- 2. Data Loading & Flattening ---
# @st.cache_data ensures the data is only loaded once, making the app fast
@st.cache_data
def load_data():
    with open('ai_refined_products.json', 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    # json_normalize flattens nested dictionaries. 
    # 'price' becomes 'price.original_price', 'price.current_price', etc.
    df = pd.json_normalize(raw_data)
    
    # Drop rows where essential data might be missing
    df = df.dropna(subset=['category', 'price.current_price'])
    return df

df = load_data()

# --- 3. UI Header ---
st.title("🛒 Metro Markets: Retail Analytics Platform")
st.markdown("A data-driven browser built to optimize assortment decisions and portfolio rationalization.")

# --- 4. Sidebar Filters ---
st.sidebar.header("Filter Options")

# Create a list of categories, adding an "All" option at the top
categories = ["All"] + sorted(list(df['category'].unique()))
selected_category = st.sidebar.selectbox("Select Category", categories)

# Apply the filter
if selected_category != "All":
    filtered_df = df[df['category'] == selected_category]
else:
    filtered_df = df

# --- 5. Key Performance Indicators (KPIs) ---
st.subheader("High-Level Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Products", len(filtered_df))
col2.metric("Average Discount", f"{filtered_df['price.discount_percentage'].mean():.1f}%")
col3.metric("Average Current Price", f"{filtered_df['price.current_price'].mean():.2f} EGP")

st.divider()

# --- 6. Visualizations (Addressing Business Benefits) ---
colA, colB = st.columns(2)

with colA:
    st.subheader("📊 Smarter Placement")
    st.markdown("Visualize inventory distribution by category and brand.")
    
    # Treemap: Great for showing hierarchical data
    fig_tree = px.treemap(
        filtered_df, 
        path=[px.Constant("All Products"), 'category', 'brand'],
        title="Product Hierarchy (Category -> Brand)"
    )
    fig_tree.update_traces(root_color="lightgrey")
    fig_tree.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    st.plotly_chart(fig_tree, use_container_width=True)

with colB:
    st.subheader("💰 Portfolio Rationalization")
    st.markdown("Identify high-margin items vs. heavily discounted stock.")
    
    # Scatter Plot: Price vs Discount
    fig_scatter = px.scatter(
        filtered_df, 
        x="price.current_price", 
        y="price.discount_percentage", 
        color="brand",
        hover_name="name", # Shows product name on hover
        title="Current Price vs. Discount Percentage",
        labels={
            "price.current_price": "Current Price (EGP)",
            "price.discount_percentage": "Discount (%)"
        }
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# --- 7. Raw Structured Data Browser ---
st.divider()
st.subheader("Raw Structured Data Browser")
st.markdown("Explore the underlying AI-classified JSON data.")

# Select a clean subset of columns to show in the table
display_cols = [
    'product_id', 'name', 'brand', 'category', 
    'price.current_price', 'price.discount_percentage', 'availability'
]
st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)