import asyncio

# The loop must exist BEFORE tfmplugins is imported
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from tfmplugins.network import NetworkScanner
from tfmplugins.network.drivers.windivert import WinDivertDriver
from tfmplugins.tfm import TFMConnection, main_ip


if __name__ == '__main__':
    network = NetworkScanner(WinDivertDriver, TFMConnection)
    network.add("main")
    print("Network scanner running.")

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        network.stop()
        print("\rBye bye!")
