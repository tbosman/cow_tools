import websockets.client
from websockets.client import WebSocketClientProtocol
import asyncio
import logging
import time
from typing import Dict, List, Union, Optional, Any, Set, MutableSet, Tuple

from settlement.datastructures import SimulationRequest
from models.batch_auction_model import SettledBatchAuction


async def sim_client():
    async with websockets.connect("ws://localhost:8001/", ping_interval=10, ping_timeout=20) as websocket:
        while True:
            sol = open('/Users/tbosman/git_tree/1inch-solver/service/sol_4202.json', 'r').read()
            msg = SimulationRequest(SettledBatchAuction.from_json(sol), True).to_json()

            await websocket.send(msg)
            response = await websocket.recv()
            print('Poing!')
            print(response)
            time.sleep(10)

if __name__ == "__main__":
    asyncio.run(sim_client())
