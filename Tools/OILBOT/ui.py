import streamlit as st
import yaml

CONFIG_FILE = "config.yaml"

st.title("Algo Trading Dashboard")

# Load config
with open(CONFIG_FILE) as f:
    config = yaml.safe_load(f)

st.sidebar.header("Strategy Settings")

# Editable controls
config['strategy']['spike_threshold'] = st.sidebar.slider(
    "Spike Threshold", 0.005, 0.05, config['strategy']['spike_threshold']
)

config['strategy']['imbalance_threshold'] = st.sidebar.slider(
    "Imbalance Threshold", 0.1, 0.8, config['strategy']['imbalance_threshold']
)

config['risk']['stop_loss'] = st.sidebar.slider(
    "Stop Loss", 0.005, 0.05, config['risk']['stop_loss']
)

config['risk']['take_profit'] = st.sidebar.slider(
    "Take Profit", 0.005, 0.05, config['risk']['take_profit']
)

# Save config
if st.sidebar.button("Save Config"):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
    st.success("Config Saved")

st.subheader("Bot Status")
st.write("Running...")


# Show logs
st.subheader("Logs")
try:
    with open("trading.log") as f:
        logs = f.readlines()[-20:]
        for line in logs:
            st.text(line)
except:
    st.write("No logs yet")