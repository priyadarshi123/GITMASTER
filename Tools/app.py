import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import numpy as np

# Download VADER lexicon for sentiment analysis
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')
sia = SentimentIntensityAnalyzer()

# Configure the Streamlit page layout
st.set_page_config(page_title="Trading Desk Dashboard", layout="wide")
st.title("Interactive Financial Comparison & Valuation Dashboard")

# --- Sidebar Inputs ---
st.sidebar.header("Dashboard Parameters")
ticker_input = st.sidebar.text_input("Select Target Company (e.g., AAPL)", value="AAPL").upper()
peers_input = st.sidebar.text_input("Peer Companies (comma-separated)", value="MSFT,GOOGL").upper()
peer_tickers = [x.strip() for x in peers_input.split(",") if x.strip()]
all_tickers = [ticker_input] + peer_tickers


# --- Data Fetching Functions ---
@st.cache_data(ttl=3600)
def get_financials(tickers):
    data = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            data.append({
                "Ticker": t,
                "P/E Ratio": info.get("trailingPE", np.nan),
                "P/B Ratio": info.get("priceToBook", np.nan),
                "Debt/Equity": info.get("debtToEquity", np.nan),
                "ROE": info.get("returnOnEquity", np.nan)
            })
        except Exception:
            pass
    return pd.DataFrame(data)


@st.cache_data(ttl=3600)
def get_technical_data(ticker):
    df = yf.Ticker(ticker).history(period="1y")
    if df.empty: return df

    # Calculate Simple Moving Averages
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()

    # Calculate Relative Strength Index (RSI)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Calculate MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

    return df


@st.cache_data(ttl=3600)
def get_news_sentiment(ticker):
    news = yf.Ticker(ticker).news
    sentiments = []
    for article in news[:10]:  # Analyze top 10 recent articles
        title = article.get("title", "")
        score = sia.polarity_scores(title)['compound']
        sentiments.append({"Title": title, "Sentiment Score": score})

    df = pd.DataFrame(sentiments)
    avg_score = df["Sentiment Score"].mean() if not df.empty else 0
    return df, avg_score


# --- Main Dashboard Execution ---
if ticker_input:
    # Section 1: Financial Comparison
    st.header(f"1. Financial Ratio Comparison: {ticker_input} vs Peers")
    fin_df = get_financials(all_tickers)

    if not fin_df.empty:
        st.dataframe(fin_df, use_container_width=True)
        try:
            target_pe = fin_df[fin_df["Ticker"] == ticker_input]["P/E Ratio"].values[0]
            peer_pe_avg = fin_df[fin_df["Ticker"] != ticker_input]["P/E Ratio"].mean()
        except IndexError:
            target_pe, peer_pe_avg = np.nan, np.nan
    else:
        st.warning("Could not fetch financial data.")
        target_pe, peer_pe_avg = np.nan, np.nan

    # Section 2: Technical Analysis
    st.header(f"2. Technical Analysis ({ticker_input})")
    tech_df = get_technical_data(ticker_input)

    if not tech_df.empty:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                            row_heights=[0.5, 0.25, 0.25])

        # Candlestick & Moving Averages
        fig.add_trace(go.Candlestick(x=tech_df.index, open=tech_df['Open'], high=tech_df['High'],
                                     low=tech_df['Low'], close=tech_df['Close'], name='Price'), row=1, col=1)
        fig.add_trace(go.Scatter(x=tech_df.index, y=tech_df['SMA_50'], name='50 SMA', line=dict(color='orange')), row=1,
                      col=1)
        fig.add_trace(go.Scatter(x=tech_df.index, y=tech_df['SMA_200'], name='200 SMA', line=dict(color='blue')), row=1,
                      col=1)

        # RSI Subplot
        fig.add_trace(go.Scatter(x=tech_df.index, y=tech_df['RSI'], name='RSI', line=dict(color='purple')), row=2,
                      col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        # MACD Subplot
        fig.add_trace(go.Scatter(x=tech_df.index, y=tech_df['MACD'], name='MACD', line=dict(color='blue')), row=3,
                      col=1)
        fig.add_trace(go.Scatter(x=tech_df.index, y=tech_df['Signal_Line'], name='Signal', line=dict(color='orange')),
                      row=3, col=1)

        fig.update_layout(height=800, title_text=f"{ticker_input} Technical Indicators")
        st.plotly_chart(fig, use_container_width=True)

        current_rsi = tech_df['RSI'].iloc[-1]
    else:
        st.warning("Could not fetch technical data.")
        current_rsi = np.nan

    # Section 3: Sentiment Analysis
    st.header(f"3. News Sentiment Analysis ({ticker_input})")
    news_df, avg_sentiment = get_news_sentiment(ticker_input)
    st.metric(label="Average Sentiment Score (-1 to 1)", value=round(avg_sentiment, 2))
    if not news_df.empty:
        st.table(news_df)

    # Section 4: Final Valuation Conclusion
    st.header(f"4. Automated Valuation Conclusion: {ticker_input}")

    score = 0
    reasons = []

    # Fundamental Logic (P/E relative to peers)
    if not pd.isna(target_pe) and not pd.isna(peer_pe_avg):
        if target_pe < peer_pe_avg * 0.9:
            score += 1
            reasons.append(f"🟢 Undervalued fundamentally (P/E {target_pe:.1f} < Peer Avg {peer_pe_avg:.1f})")
        elif target_pe > peer_pe_avg * 1.1:
            score -= 1
            reasons.append(f"🔴 Overvalued fundamentally (P/E {target_pe:.1f} > Peer Avg {peer_pe_avg:.1f})")
        else:
            reasons.append(f"🟡 Fairly valued fundamentally vs peers")

    # Technical Logic (RSI Overbought/Oversold)
    if not pd.isna(current_rsi):
        if current_rsi < 30:
            score += 1
            reasons.append(f"🟢 Oversold technically (RSI {current_rsi:.1f} < 30)")
        elif current_rsi > 70:
            score -= 1
            reasons.append(f"🔴 Overbought technically (RSI {current_rsi:.1f} > 70)")
        else:
            reasons.append(f"🟡 Technically neutral (RSI {current_rsi:.1f})")

    # Sentiment Logic (VADER Compound Score)
    if avg_sentiment > 0.15:
        score += 1
        reasons.append(f"🟢 Bullish News Sentiment (Score: {avg_sentiment:.2f})")
    elif avg_sentiment < -0.15:
        score -= 1
        reasons.append(f"🔴 Bearish News Sentiment (Score: {avg_sentiment:.2f})")
    else:
        reasons.append(f"🟡 Neutral News Sentiment")

    # Final Decision Output
    st.subheader("Conclusion:")
    if score >= 1:
        st.success(f"**UNDER VALUED** - Strong buy signals detected.")
    elif score <= -1:
        st.error(f"**OVER VALUED** - Strong sell/avoid signals detected.")
    else:
        st.info(f"**FAIR VALUED** - Asset appears fairly priced with mixed or neutral signals.")

    for r in reasons:
        st.write(r)