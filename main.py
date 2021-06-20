import logging
from config import *

from connectors.bitmex import BitmexClient
from connectors.binance import BinanceClient

from interface.root_component import Root

logger = logging.getLogger()

logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler()
file_handler = logging.FileHandler("info.log")

formatter = logging.Formatter('%(asctime)s %(levelname)s :: %(message)s')

stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

if __name__ == "__main__":
    binance = BinanceClient(
        BINANCE_SPOT_KEY_TESTNET,
        BINANCE_SPOT_SECRET_TESTNET,
        testnet=True,
        futures=False)

    bitmex = BitmexClient(
        BITMEX_KEY,
        BITMEX_SECRET,
        testnet=True
    )

    root = Root(binance, bitmex)
    root.mainloop()
