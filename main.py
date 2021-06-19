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
        BINANCE_SPOT_KEY,
        BINANCE_SPOT_SECRET,
        True, False)

    bitmex = BitmexClient(
        BITMEX_KEY,
        BINANCE_SPOT_SECRET,
        True
    )


    root = Root(binance, bitmex)
    root.mainloop()

####################################
# bitmex_contracts = get_contracts()
# root.configure(bg="gray12")
# i=0
# j=0
# calibri_font = ("Calibri", 11, "normal")
# for contract in bitmex_contracts:
#     label_widget = tk.Label(root, text=contract, bg="gray12", fg="SteelBlue1", width=13, font=calibri_font)
#     #label_widget.pack(side=tk.TOP)
#     #label_widget.pack(side=tk.BOTTOM)
#     #label_widget.pack(side=tk.LEFT)
#     #label_widget.pack(side=tk.RIGHT)
#     label_widget.grid(row=i, column=j, sticky="ew")
#     if i == 4:
#         j += 1
#         i = 0
#     else:
#         i += 1

###################################
# print(binance.get_contracts())
# print(binance.get_bid_ask("BTCUSDT"))
# print(binance.get_historical_candles("BTCUSDT", "1h"))
# print(binance.get_balances())
# print(binance.place_order("BTCUSDT", "BUY", 0.01, "LIMIT", 2000, "GTC"))
# print(binance.get_order_status("BTCUSDT", 2694437026))
# print(binance.cancel_order("BTCUSDT", 2694437026))
