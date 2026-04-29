def create_features(df):
    df['returns'] = df['price'].pct_change()
    df['volatility'] = df['returns'].rolling(window=10).std()
    df['momentum'] = df['price'].pct_change(5)
    df['volume_spike'] = df['volume'] / df['volume'].rolling(20).mean()
    df['imbalance_ma'] = df['imbalance'].rolling(5).mean()
    df = df.dropna()
    return df