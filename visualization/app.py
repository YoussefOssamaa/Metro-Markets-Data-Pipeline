import streamlit as st
import pandas as pd
import plotly.express as px
import json

# --- 1. App Configuration ---
st.set_page_config(page_title="Metro Markets Analytics", layout="wide", page_icon="🛒")

# --- 2. Data Loading & Flattening ---
@st.cache_data
def load_data():
    with open('ai_refined_products.json', 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    # json_normalize flattens nested dictionaries. 
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

# Handle cases where the discount column might be completely missing/NaN
avg_discount = filtered_df['price.discount_percentage'].mean() if 'price.discount_percentage' in filtered_df.columns else 0
col2.metric("Average Discount", f"{avg_discount:.1f}%")

col3.metric("Average Current Price", f"{filtered_df['price.current_price'].mean():.2f} EGP")

st.divider()

# --- 6. Visualizations (Addressing Business Benefits) ---
# ROW 1: Existing Charts
colA, colB = st.columns(2)

with colA:
    st.subheader("📊 Smarter Placement")
    st.markdown("Visualize inventory distribution by category and brand.")
    
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
    
    fig_scatter = px.scatter(
        filtered_df, 
        x="price.current_price", 
        y="price.discount_percentage", 
        color="brand",
        hover_name="name",
        title="Current Price vs. Discount Percentage",
        labels={
            "price.current_price": "Current Price (EGP)",
            "price.discount_percentage": "Discount (%)"
        }
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# ROW 2: New Charts (Pie & Bar)
colC, colD = st.columns(2)
with colC:
    st.subheader("🥧 Product Distribution")
    st.markdown("Understand the makeup of your current inventory view.")
    
    # Smart logic: Show categories if "All" is selected, otherwise show brands in that category
    if selected_category == "All":
        pie_names = 'category'
        pie_title = "Product Distribution by Category"
    else:
        pie_names = 'brand'
        pie_title = f"Brand Distribution within '{selected_category}'"

    # Build distribution table and group tiny slices (<2%) into "Other"
    distribution_df = (
        filtered_df[pie_names]
        .fillna("Unknown")
        .astype(str)
        .value_counts()
        .rename_axis("label")
        .reset_index(name="count")
    )
    distribution_df["percentage"] = (distribution_df["count"] / distribution_df["count"].sum()) * 100

    small_items_df = distribution_df[distribution_df["percentage"] < 3].copy()
    main_items_df = distribution_df[distribution_df["percentage"] >= 3].copy()

    if not small_items_df.empty:
        other_row = pd.DataFrame([
            {
                "label": "Other",
                "count": int(small_items_df["count"].sum()),
                "percentage": float(small_items_df["percentage"].sum())
            }
        ])
        pie_df = pd.concat([main_items_df, other_row], ignore_index=True)
    else:
        pie_df = main_items_df

    fig_pie = px.pie(
        pie_df,
        names="label",
        values="count",
        title=pie_title,
        hole=0.4  # Makes it a donut chart, which usually looks a bit cleaner
    )
    fig_pie.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

    if not small_items_df.empty:
        st.caption("Items contributing less than 3% are grouped into `Other`.")

        drill_options = ["None", "Other"]
        selected_drill = st.selectbox(
            "Drill-down view",
            options=drill_options,
            index=0,
            key=f"other_drill_{selected_category}"
        )

        if selected_drill == "Other":
            other_details = small_items_df.sort_values("percentage", ascending=False).copy()

            fig_other = px.bar(
                other_details,
                x="label",
                y="percentage",
                title="Breakdown of items grouped in 'Other'",
                labels={
                    "label": "Category/Brand",
                    "percentage": "Share (%)"
                }
            )
            st.plotly_chart(fig_other, use_container_width=True)

            st.dataframe(
                other_details[["label", "count", "percentage"]].rename(
                    columns={
                        "label": "Item",
                        "count": "Products",
                        "percentage": "Share (%)"
                    }
                ),
                use_container_width=True,
                hide_index=True
            )

with colD:
    st.subheader("📈 Avg Discount by Price Range")
    st.markdown("See how discount behavior changes across product price ranges.")
    
    # Build price-range buckets and compute average discount for each range
    if 'price.discount_percentage' in filtered_df.columns:
        price_discount_df = filtered_df[['price.current_price', 'price.discount_percentage']].dropna().copy()

        if not price_discount_df.empty and price_discount_df['price.current_price'].nunique() > 1:
            # Dynamic, data-driven buckets (up to 8) for readable ranges
            num_bins = min(8, price_discount_df['price.current_price'].nunique())

            min_price = float(price_discount_df['price.current_price'].min())
            max_price = float(price_discount_df['price.current_price'].max())

            bin_edges = pd.interval_range(start=min_price, end=max_price, periods=num_bins)

            if len(bin_edges) > 0:
                bins = [bin_edges[0].left] + [interval.right for interval in bin_edges]

                price_discount_df['price_range'] = pd.cut(
                    price_discount_df['price.current_price'],
                    bins=bins,
                    include_lowest=True,
                    duplicates='drop'
                )

                range_stats = (
                    price_discount_df
                    .groupby('price_range', observed=True)
                    .agg(
                        avg_discount=('price.discount_percentage', 'mean'),
                        products=('price.discount_percentage', 'size')
                    )
                    .reset_index()
                )

                range_stats['price_range_label'] = range_stats['price_range'].apply(
                    lambda r: f"{r.left:.0f} - {r.right:.0f} EGP"
                )

                fig_bar = px.bar(
                    range_stats,
                    x='price_range_label',
                    y='avg_discount',
                    color='avg_discount',
                    title='Average Discount by Price Range',
                    labels={
                        'price_range_label': 'Price Range',
                        'avg_discount': 'Avg Discount (%)'
                    },
                    color_continuous_scale='Viridis'
                )
                fig_bar.update_layout(xaxis_tickangle=-30)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Not enough variation in price data to build price ranges.")
        else:
            st.info("Not enough price + discount data to analyze ranges.")
    else:
        st.info("Discount data not available for this selection.")

# --- 7. Raw Structured Data Browser ---
st.divider()
st.subheader("Raw Structured Data Browser")
st.markdown("Explore the underlying AI-classified JSON data.")

# Select a clean subset of columns to show in the table
display_cols = [
    'product_id', 'name', 'brand', 'category', 
    'price.current_price', 'price.discount_percentage', 'availability'
]
# Only include columns that actually exist in the dataframe to prevent errors
existing_cols = [col for col in display_cols if col in filtered_df.columns]

st.dataframe(filtered_df[existing_cols], use_container_width=True, hide_index=True)
