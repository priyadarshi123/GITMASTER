import asyncio
import yaml
from logger import setup_logger
from data import DataHandler,TickRecorder
from strategy import Strategy
from risk import RiskManager
from execution import Execution


with open("config.yaml") as f:
    config = yaml.safe_load(f)

logger = setup_logger()

data = DataHandler(config)

strategy = Strategy(config)
risk = RiskManager(config)
execution = Execution(data.ib, data.contract, config)


recorder = TickRecorder()


async def trading_loop():
    logger.info("Bot started")

    while True:
        try:
            price = data.get_price()
            depth = data.get_order_book()

            imbalance = data.get_imbalance(depth)
            news_signal = data.get_news_signal()
            recorder.record_tick(price, 0, imbalance)

            signal = strategy.generate_signal(price, imbalance, news_signal)

            logger.info(f"{price} | {imbalance} | {news_signal} | {signal}")

            if signal != "NO_TRADE" and risk.can_trade():
                #execution.place_bracket_order(signal, price)
                risk.record_trade()

            await asyncio.sleep(2)




        except Exception as e:
            logger.error(str(e))
            await asyncio.sleep(2)


try:
    asyncio.run(trading_loop())
finally:
    recorder.close()
    logger.info("Flushed remaining tick data to parquet file")
