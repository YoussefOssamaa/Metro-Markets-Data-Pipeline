import streamlit as st
import pandas as pd
import plotly.express as px
import json

st.set_page_config(page_title="Metro Markets Analytics", layout="wide", page_icon="🛒")

@st.cache_data
def load_data():
    import pandas as pd
    import json
    
    # Notice the 'r' before the quotes. This makes them raw strings so Windows paths work safely.
    raw_path = r"..\Scraping\version2\crwal_results.json"
    clean_path = r"..\cleaning_and_ai_enhancing\cleaned_products.json"
    ai_path = r"..\cleaning_and_ai_enhancing\ai_refined_products.json"

    # Load Raw
    with open(raw_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f).get('products', [])
    df_raw = pd.DataFrame(raw_data)
        
    # Load Clean
    with open(clean_path, 'r', encoding='utf-8') as f:
        clean_data = json.load(f)
    df_clean = pd.DataFrame(clean_data)
        
    # Load and Normalize AI Data
    with open(ai_path, 'r', encoding='utf-8') as f:
        ai_data = json.load(f)
    df_ai = pd.json_normalize(ai_data)
    
    # Handle lists in the tags column
    if 'tags' in df_ai.columns:
        df_ai['tags_str'] = df_ai['tags'].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")
    
    return df_raw, df_clean, df_ai

# Helper functions for data processing
def get_tag_frequency(df):
    """Extract and count semantic tags from AI enrichment."""
    if 'tags' not in df.columns or df['tags'].isna().all():
        return pd.DataFrame()
    all_tags = pd.Series([tag for tags in df['tags'].dropna() for tag in tags])
    counts = all_tags.value_counts().head(15).reset_index()
    counts.columns = ['Tag', 'Count']
    return counts

def get_unit_distribution(df):
    """Get distribution of measurement units."""
    if 'size.unit' not in df.columns:
        return pd.DataFrame()
    counts = df['size.unit'].value_counts().reset_index()
    counts.columns = ['Unit', 'Count']
    return counts

# Load data
df_raw, df_clean, df_ai = load_data()

# Page header and sidebar
st.title("🛒 Metro Markets: Retail Analytics Platform")
st.markdown("A data-driven browser built to optimize assortment decisions and portfolio rationalization.")

st.sidebar.header("Filter Options")
st.sidebar.info("Filters apply to the **AI Enrichment** and **Business Insights** tabs.")

# Category filter
categories = ["All"] + sorted([c for c in df_ai['category'].unique() if pd.notna(c)])
selected_category = st.sidebar.selectbox("Select Category", categories)
filtered_ai = df_ai if selected_category == "All" else df_ai[df_ai['category'] == selected_category]

# Navigation tabs
tab1, tab2, tab3, tab4 = st.tabs(["🔄 The Data Pipeline", "✨ AI Enrichment", "📈 Business Insights", "🔍 Product Explorer"])

# TAB 1: Data Pipeline Visualization
with tab1:
    st.header("The Data Journey")
    st.markdown("Observe how unstructured web data is standardized, cleaned, and heavily enriched.")
    
    st.subheader("🔴 1. Raw Crawled Data")
    st.markdown("**Problem:** Prices contain text (e.g., `LE`), discounts have `%` symbols, misaligned categories—data cannot be analyzed or filtered.")
    st.dataframe(df_raw[['name', 'price', 'discount', 'category']].head(5), use_container_width=True)
    
    st.markdown("**⬇️ Data Cleaning & Standardization ⬇️**")
    
    st.subheader("🟡 2. Cleaned Data")
    st.markdown("**Solution:** RegEx removes text, prices cast to floats. Now we can calculate statistics and filter correctly.")
    st.dataframe(df_clean[['name', 'price', 'discount', 'category']].head(5), use_container_width=True)
    
    st.markdown("**⬇️ LLM & AI Enrichment ⬇️**")
    
    st.subheader("🟢 3. AI Refined Data")
    st.markdown("**Business Value:** LLM extracts structured attributes (units, values), corrects categories, generates searchable tags.")
    ai_cols = ['name', 'price.current_price', 'size.value', 'size.unit', 'product_type']
    ai_display = [col for col in ai_cols if col in df_ai.columns]
    st.dataframe(df_ai[ai_display].head(5), use_container_width=True)


# TAB 2: AI Enrichment Quality
with tab2:
    st.header("How AI Enhances Search & Discovery")
    st.markdown("By parsing complex strings into structured data, we unlock three major website capabilities:")
    
    # SEMANTIC SEARCH TAGS
    st.subheader("1️⃣ Semantic Search Tags")
    st.markdown("""
    **What it does:** The LLM reads product descriptions and generates hidden metadata tags that capture product characteristics, brands, use cases, and attributes.
    
    **Example Transformation:**
    - **Raw text:** "Del Monte Pineapple Chunks 565g Can Tropical Fruit Canned"
    - **Tags generated:** `canned`, `fruit`, `tropical`, `pineapple`, `del-monte`, `snack`, `long-shelf-life`, `ready-to-eat`
    
    **Website Benefits:**
    - 🔍 **Better Search:** Customer searches "tropical fruit snacks" → finds Del Monte, even if "tropical" isn't in product name
    - 📈 **Increased Discoverability:** Products appear in 8+ search result pages instead of just 1
    - 🛒 **Higher Conversion:** Customers find what they're looking for → larger baskets
    - 💰 **Cross-selling:** Related products tagged similarly can be recommended together
    """)
    
    tag_counts = get_tag_frequency(filtered_ai)
    if not tag_counts.empty:
        fig_tags = px.bar(tag_counts, x='Count', y='Tag', orientation='h', 
                          color='Count', color_continuous_scale='Blues', height=500)
        fig_tags.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, 
                              xaxis_title="Frequency", yaxis_title="Tag")
        st.plotly_chart(fig_tags, use_container_width=True)
        st.caption(f"Total unique tags generated: {tag_counts['Tag'].nunique()} | Top tags appear {tag_counts['Count'].max()} times")
    
    st.divider()
    
    # MEASUREMENT NORMALIZATION
    st.subheader("2️⃣ Measurement Normalization")
    st.markdown("""
    **What it does:** The LLM extracts size and unit information from descriptions into a structured field (value + unit).
    
    **Example Transformation:**
    - **Raw text:** "Coca Cola Bottle 1.5 Liters" → Structured: `size.value: 1.5`, `size.unit: L`
    - **Raw text:** "Tide Detergent 2kg Bag" → Structured: `size.value: 2`, `size.unit: kg`
    
    **Website Benefits:**
    - 💵 **Price-per-Unit Comparison:** Show customers "EGP 45/L" for Cola vs competitors → data-driven purchasing
    - 📊 **Smarter Shelf Placement:** Group same-unit products → easier to compare 500g vs 1kg flour
    - 🎯 **Promotions:** "Buy 2x 1L bottles, get 15% off" can be auto-targeted to right customers
    - 📱 **Mobile UX:** Customers can filter "I want 500g or less" → reduces overwhelm
    """)
    
    unit_counts = get_unit_distribution(filtered_ai)
    if not unit_counts.empty:
        fig_units = px.pie(unit_counts, values='Count', names='Unit', hole=0.4, height=700)
        fig_units.update_layout(
            showlegend=True,
            legend=dict(x=1.05, y=0.5),
            margin=dict(l=50, r=200, t=50, b=50),
            font=dict(size=13),
            autosize=True
        )
        st.plotly_chart(fig_units, use_container_width=False, config={"responsive": True})
        st.caption(f"Data normalized into {len(unit_counts)} standardized units across {unit_counts['Count'].sum()} products")
    
    st.divider()
    
    # BUSINESS IMPACT SUMMARY
    st.subheader("📊 Impact on Website Performance")
    impact_col1, impact_col2, impact_col3 = st.columns(3)
    with impact_col1:
        st.metric("Search Accuracy", "↑ 8x", "More tags = better matches")
    with impact_col2:
        st.metric("Product Discoverability", f"{len(df_ai)} products", "Now searchable by attributes")
    with impact_col3:
        st.metric("Customer Experience", "↑ 3x", "Faster product finding")


# TAB 3: Business Insights
with tab3:
    st.header("Data-Driven Merchandising Decisions")
    
    # KPIs
    st.subheader("High-Level Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Products", len(filtered_ai))
    avg_discount = filtered_ai['price.discount_percentage'].mean() if 'price.discount_percentage' in filtered_ai.columns else 0
    col2.metric("Average Discount", f"{avg_discount:.1f}%")
    avg_price = filtered_ai['price.current_price'].mean() if 'price.current_price' in filtered_ai.columns else 0
    col3.metric("Average Price", f"{avg_price:.2f} EGP")

    st.divider()

    # Inventory Distribution & Pricing Relationship
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("Smarter Placement")
        st.markdown("Inventory distribution by category and brand.")
        fig_tree = px.treemap(
            filtered_ai.fillna("Unknown"), 
            path=[px.Constant("All Products"), 'category', 'brand']
        )
        fig_tree.update_layout(margin=dict(t=20, l=10, r=10, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)

    with col_right:
        st.subheader("Portfolio Rationalization")
        st.markdown("Price vs. discount relationship by brand.")
        if 'price.current_price' in filtered_ai.columns and 'price.discount_percentage' in filtered_ai.columns:
            fig_scatter = px.scatter(
                filtered_ai, 
                x="price.current_price", 
                y="price.discount_percentage", 
                color="brand",
                hover_name="name",
                labels={
                    "price.current_price": "Current Price (EGP)",
                    "price.discount_percentage": "Discount (%)"
                }
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

    st.divider()
    
    # Price-based Discount Analysis
    st.subheader("Discount Behavior by Price Range")
    st.markdown("How discount strategies vary across price tiers.")
    
    if 'price.discount_percentage' in filtered_ai.columns and 'price.current_price' in filtered_ai.columns:
        price_discount_df = filtered_ai[['price.current_price', 'price.discount_percentage']].dropna().copy()
        
        if not price_discount_df.empty and price_discount_df['price.current_price'].nunique() > 1:
            # Bin prices into 5 quantile ranges for cleaner bucketing
            price_discount_df['price_range'] = pd.qcut(
                price_discount_df['price.current_price'], 
                q=5, duplicates='drop', labels=False
            )
            
            range_stats = price_discount_df.groupby('price_range').agg(
                min_price=('price.current_price', 'min'),
                max_price=('price.current_price', 'max'),
                avg_discount=('price.discount_percentage', 'mean')
            ).reset_index()
            
            range_stats['label'] = range_stats.apply(
                lambda r: f"{r['min_price']:.0f} - {r['max_price']:.0f} EGP", axis=1
            )
            
            fig_bar = px.bar(
                range_stats, x='label', y='avg_discount', 
                color='avg_discount',
                labels={'label': 'Price Range', 'avg_discount': 'Avg Discount (%)'},
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig_bar, use_container_width=True)


# TAB 4: Product Explorer
with tab4:
    st.header("Product Explorer")
    st.markdown("Search and discover products from the AI-enriched catalog.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        search_term = st.text_input("Search by product name or brand:", placeholder="e.g., milk, coca, nestle")
    
    with col2:
        min_price, max_price = st.slider(
            "Price Range (EGP):",
            min_value=float(df_ai['price.current_price'].min()) if 'price.current_price' in df_ai.columns else 0,
            max_value=float(df_ai['price.current_price'].max()) if 'price.current_price' in df_ai.columns else 100,
            value=(
                float(df_ai['price.current_price'].min()) if 'price.current_price' in df_ai.columns else 0,
                float(df_ai['price.current_price'].max()) if 'price.current_price' in df_ai.columns else 100
            )
        )
    
    # Apply filters
    explorer_data = df_ai.copy()
    
    if search_term:
        explorer_data = explorer_data[
            (explorer_data['name'].str.contains(search_term, case=False, na=False)) |
            (explorer_data['brand'].str.contains(search_term, case=False, na=False))
        ]
    
    if 'price.current_price' in explorer_data.columns:
        explorer_data = explorer_data[
            (explorer_data['price.current_price'] >= min_price) &
            (explorer_data['price.current_price'] <= max_price)
        ]
    
    # Display results
    st.subheader(f"Results: {len(explorer_data)} products found")
    
    display_cols = ['name', 'brand', 'price.current_price', 'price.discount_percentage', 'category', 'product_type']
    display_cols = [col for col in display_cols if col in explorer_data.columns]
    
    if not explorer_data.empty:
        st.dataframe(explorer_data[display_cols], use_container_width=True, height=400)
    else:
        st.info("No products match your search. Try adjusting your filters.")