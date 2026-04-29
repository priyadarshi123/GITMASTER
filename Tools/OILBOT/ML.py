from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split



def create_features(df):
    df['returns'] = df['price'].pct_change()

    df['volatility'] = df['returns'].rolling(10).std()

    df['momentum'] = df['price'].pct_change(5)

    df['volume_spike'] = df['volume'] / df['volume'].rolling(20).mean()

    df['imbalance_ma'] = df['imbalance'].rolling(5).mean()

    df = df.dropna()
    return df

def create_labels(df, horizon=3):
    df['future_return'] = df['price'].shift(-horizon) / df['price'] - 1

    df['target'] = 0
    df.loc[df['future_return'] > 0.002, 'target'] = 1
    df.loc[df['future_return'] < -0.002, 'target'] = -1

    return df.dropna()

def train_model(df):
    features = ['returns', 'volatility', 'momentum', 'volume_spike', 'imbalance_ma']

    X = df[features]
    y = df['target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = RandomForestClassifier(n_estimators=100, max_depth=5)
    model.fit(X_train, y_train)

    print("Train Accuracy:", model.score(X_train, y_train))
    print("Test Accuracy:", model.score(X_test, y_test))

    return model