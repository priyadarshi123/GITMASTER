"""
PE Ratio Analysis Dashboard - Major Global Indexes
This page fetches and visualizes moving PE ratio trends for major stock indexes
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

import yfinance as yf


@st.cache_data(ttl=3600, show_spinner="Fetching PE ratio data...")
def fetch_pe_ratio_data(ticker, years=10):
    """
    Fetch PE ratio data for an index/stock using yfinance.
    Returns a DataFrame with date and P/E ratio.

    Args:
        ticker (str): Yahoo Finance ticker symbol
        years (int): Number of years of historical data to fetch

    Returns:
        DataFrame: Index date, PE ratio values
    """
    try:
        # Fetch historical data
        data = yf.download(ticker, period=f"{years}y", progress=False)

        if data.empty:
            st.warning(f"No data found for {ticker}")
            return pd.DataFrame()

        # Try to get PE ratio from info
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info

        # Create a series with available PE ratio data
        # Note: yfinance doesn't provide historical PE, so we'll calculate from available data
        pe_data = pd.DataFrame()
        pe_data['Close'] = data['Close']

        # Try to extract EPS from ticker info for current calculation
        if 'trailingEps' in info:
            current_pe = info.get('trailingPE', np.nan)
            pe_data['CurrentPE'] = current_pe

        return pe_data
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner="Computing moving PE ratios...")
def calculate_moving_pe_ratio(ticker, window=90):
    """
    Calculate moving average PE ratio for an index.
    Uses yfinance fundamental data and price data.

    Args:
        ticker (str): Yahoo Finance ticker
        window (int): Days for moving average window

    Returns:
        DataFrame: Date and moving PE ratio
    """
    try:
        ticker_obj = yf.Ticker(ticker)

        # Get historical data
        hist = yf.download(ticker, period="10y", progress=False)

        if hist.empty:
            return pd.DataFrame()

        # Get current PE ratio from info
        info = ticker_obj.info
        current_pe = info.get('trailingPE', np.nan)

        # Create DataFrame with price and estimated PE (simplified approach)
        result = pd.DataFrame(index=hist.index)
        result['Close'] = hist['Close']
        result['PE_Ratio'] = np.nan  # Will be filled below

        # Apply moving average to close prices (proxy for PE movement)
        result['MA_Close'] = result['Close'].rolling(window=window).mean()

        # Normalize to show PE movement pattern
        if not result['MA_Close'].isna().all():
            result['PE_Proxy'] = (result['MA_Close'] / result['MA_Close'].iloc[0]) * current_pe

        return result.dropna()

    except Exception as e:
        st.error(f"Error calculating moving PE for {ticker}: {str(e)}")
        return pd.DataFrame()


def plot_pe_ratio_comparison(pe_data_dict, title="Moving PE Ratio Comparison"):
    """
    Plot PE ratio trends for multiple indexes.

    Args:
        pe_data_dict (dict): Dictionary with index names and their PE data
        title (str): Chart title
    """
    fig, ax = plt.subplots(figsize=(14, 7))

    for index_name, pe_df in pe_data_dict.items():
        if not pe_df.empty and 'PE_Proxy' in pe_df.columns:
            ax.plot(pe_df.index, pe_df['PE_Proxy'], label=index_name, linewidth=2)

    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('PE Ratio (Proxy)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()

    return fig


def plot_pe_ratio_interactive(pe_data_dict):
    """
    Create interactive Plotly visualization of PE ratios.

    Args:
        pe_data_dict (dict): Dictionary with index names and their PE data
    """
    fig = px.line()

    for index_name, pe_df in pe_data_dict.items():
        if not pe_df.empty and 'PE_Proxy' in pe_df.columns:
            fig.add_scatter(
                x=pe_df.index,
                y=pe_df['PE_Proxy'],
                name=index_name,
                mode='lines'
            )

    fig.update_layout(
        title="Moving PE Ratio Trends - Major Global Indexes",
        xaxis_title="Date",
        yaxis_title="PE Ratio (Proxy)",
        hovermode='x unified',
        template='plotly_white',
        height=600
    )

    return fig


@st.cache_data(ttl=3600)
def get_index_pe_data(index_dict):
    """
    Fetch PE ratio data for multiple indexes efficiently.

    Args:
        index_dict (dict): Dictionary of {display_name: ticker}

    Returns:
        dict: {display_name: DataFrame with PE data}
    """
    results = {}

    for name, ticker in index_dict.items():
        try:
            pe_df = calculate_moving_pe_ratio(ticker, window=90)
            if not pe_df.empty:
                results[name] = pe_df
                st.write(f"✅ Loaded {name}")
            else:
                st.warning(f"⚠️ No data for {name}")
        except Exception as e:
            st.error(f"❌ Error loading {name}: {str(e)}")

    return results

st.set_page_config(layout="wide")

# Page title
st.title("📊 Global Index PE Ratio Analysis")
st.markdown("---")

# Define major global indexes
MAJOR_INDEXES = {
    "S&P 500 (USA)": "^GSPC",
    "NIFTY 50 (India)": "^NSEI",
    "Nikkei 225 (Japan)": "^N225",
    "STI (Singapore)": "^STI",
    "FTSE 100 (UK)": "^FTSE",
    "DAX (Germany)": "^GDAXI",
    "CAC 40 (France)": "^FCHI",
}

# Sidebar controls
st.sidebar.subheader("📈 Configuration")

# Select indexes to compare
selected_indexes = st.sidebar.multiselect(
    "Select Indexes to Compare:",
    options=MAJOR_INDEXES.keys(),
    #default=["S&P 500 (USA)", "NIFTY 50 (India)", "Nikkei 225 (Japan)", "STI (Singapore)","AAPL"]
    default=["AAPL"]
)

# Select moving average window
ma_window = st.sidebar.slider(
    "Moving Average Window (days):",
    min_value=30,
    max_value=365,
    value=90,
    step=15
)

# Select history period
history_years = st.sidebar.slider(
    "Historical Data (years):",
    min_value=1,
    max_value=10,
    value=5,
    step=1
)

st.sidebar.markdown("---")
st.sidebar.info(
    """
    **About PE Ratios:**
    - P/E Ratio = Stock Price / Earnings Per Share
    - Higher PE = Market prices in faster future growth
    - Lower PE = Market values at discount (potential value)
    - Useful for comparing valuation across markets
    """
)

# Main content
if not selected_indexes:
    st.warning("⚠️ Please select at least one index from the sidebar")
    st.stop()

# Create a filtered index dict
filtered_indexes = {name: ticker for name, ticker in MAJOR_INDEXES.items() if name in selected_indexes}

st.markdown("### 📥 Loading Data...")
with st.spinner("Fetching PE ratio data for selected indexes..."):
    # Load data for selected indexes
    pe_data = {}

    progress_bar = st.progress(0)
    total_indexes = len(filtered_indexes)

    for idx, (name, ticker) in enumerate(filtered_indexes.items()):
        try:
            st.write(f"⏳ Loading {name} ({ticker})...")
            print(ticker)
            pe_df = calculate_moving_pe_ratio(ticker, window=ma_window)
            print(pe_df.tail())

            if not pe_df.empty:
                pe_data[name] = pe_df
                st.success(f"✅ {name} loaded successfully")
            else:
                st.warning(f"⚠️ No data available for {name}")

        except Exception as e:
            st.error(f"❌ Error loading {name}: {str(e)}")

        progress_bar.progress((idx + 1) / total_indexes)

st.markdown("---")

# Display results
if not pe_data:
    st.error("❌ No data could be loaded. Please check your internet connection or try different indexes.")
    st.stop()

# Tabs for different visualizations
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Interactive Chart", "📈 Comparison View", "📋 Data Table", "📌 Summary Statistics"]
)

with tab1:
    st.subheader("Interactive PE Ratio Trends")
    st.markdown("Hover over the chart to see exact values. Use legend to toggle indexes on/off.")

    # Create interactive plotly chart
    fig = go.Figure()

    for index_name, pe_df in pe_data.items():
        if 'PE_Proxy' in pe_df.columns:
            fig.add_trace(go.Scatter(
                x=pe_df.index,
                y=pe_df['PE_Proxy'],
                name=index_name,
                mode='lines',
                hovertemplate=f"<b>{index_name}</b><br>Date: %{{x|%Y-%m-%d}}<br>PE Proxy: %{{y:.2f}}<extra></extra>"
            ))

    fig.update_layout(
        title=f"Moving PE Ratio Trends (MA Window: {ma_window} days)",
        xaxis_title="Date",
        yaxis_title="PE Ratio (Proxy Value)",
        hovermode='x unified',
        template='plotly_white',
        height=600,
        font=dict(size=12)
    )

    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Comparative Analysis - Matplotlib View")

    # Create matplotlib comparison
    fig = plot_pe_ratio_comparison(
        pe_data,
        title=f"PE Ratio Comparison - {', '.join(selected_indexes)}"
    )
    st.pyplot(fig)

with tab3:
    st.subheader("Detailed Data Tables")

    # Show data for each selected index
    for index_name, pe_df in pe_data.items():
        with st.expander(f"📋 {index_name} - Full Data", expanded=False):
            # Show latest 20 records
            st.write(f"**Latest 20 records for {index_name}:**")
            display_df = pe_df.tail(20).copy()
            display_df.index = display_df.index.strftime('%Y-%m-%d')
            st.dataframe(display_df, use_container_width=True)

            # Download button
            csv_data = pe_df.to_csv()
            st.download_button(
                label=f"⬇️ Download {index_name} Data (CSV)",
                data=csv_data,
                file_name=f"{index_name.replace(' ', '_')}_pe_ratio.csv",
                mime="text/csv"
            )

with tab4:
    st.subheader("📊 Summary Statistics")

    summary_data = []

    for index_name, pe_df in pe_data.items():
        if 'PE_Proxy' in pe_df.columns:
            pe_series = pe_df['PE_Proxy'].dropna()

            summary_data.append({
                "Index": index_name,
                "Current PE": f"{pe_series.iloc[-1]:.2f}" if len(pe_series) > 0 else "N/A",
                "Average PE": f"{pe_series.mean():.2f}" if len(pe_series) > 0 else "N/A",
                "Min PE": f"{pe_series.min():.2f}" if len(pe_series) > 0 else "N/A",
                "Max PE": f"{pe_series.max():.2f}" if len(pe_series) > 0 else "N/A",
                "Std Dev": f"{pe_series.std():.2f}" if len(pe_series) > 0 else "N/A",
                "Data Points": len(pe_series)
            })

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)

    # Key insights
    st.markdown("### 🔍 Key Insights")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Highest Current PE:**")
        if summary_df['Current PE'].notna().any():
            # Parse and find max
            current_pes = []
            for idx, row in summary_df.iterrows():
                try:
                    current_pes.append((row['Index'], float(row['Current PE'])))
                except:
                    pass

            if current_pes:
                max_idx, max_pe = max(current_pes, key=lambda x: x[1])
                st.info(f"**{max_idx}**: {max_pe:.2f}")

    with col2:
        st.markdown("**Lowest Current PE:**")
        if summary_df['Current PE'].notna().any():
            current_pes = []
            for idx, row in summary_df.iterrows():
                try:
                    current_pes.append((row['Index'], float(row['Current PE'])))
                except:
                    pass

            if current_pes:
                min_idx, min_pe = min(current_pes, key=lambda x: x[1])
                st.info(f"**{min_idx}**: {min_pe:.2f}")

st.markdown("---")
st.markdown("""
### 📚 Additional Information

**PE Ratio Interpretation:**
- **PE < 15**: Often considered undervalued (market pricing in lower growth)
- **PE 15-25**: Historical average range for developed markets
- **PE > 25**: Often considered overvalued (market pricing in strong future growth)

**Regional Variations:**
- Emerging markets typically have lower average P/E ratios
- Developed markets (US, UK) typically have higher P/E ratios
- Differences reflect market expectations and economic conditions

**Note:** The PE Proxy shown here is a normalized representation of price movements. 
For precise PE ratios, consider using financial data providers like Bloomberg or FactSet.
""")

st.info("**Last Updated:** Cached for 1 hour. Data refreshes automatically.")

