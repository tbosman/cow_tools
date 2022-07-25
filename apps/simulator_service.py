import asyncio
import argparse

from settlement.datastructures import SimulationResult, SimulationRequest
from util.defaultlogging import *

from websockets import WebSocketServerProtocol
import websockets.server
from concurrent.futures import ThreadPoolExecutor

from settlement.solution_simulator import SettlementSimulator

logger = logging.getLogger(__name__)
sockets = set()

executor = ThreadPoolExecutor(max_workers=30)


all_tasks = []


async def simulate_and_respond(
    simulator, batch_json, queue, estimate_block=False
):
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            executor, simulator.simulate_gas, batch_json, estimate_block
        )

        logger.info(f'Simulation passed: {result["passed"]} \n {result}')
        if result["passed"]:
            logger.info(f'Gas estimate: {result["gas"]}')
        msg = SimulationResult(batch_json, **result)
        logger.info(f"Returning message {msg}")

        await queue.put(msg)

    except:
        logger.exception("Bla")


async def rcv_msg(
    websocket: WebSocketServerProtocol, simulator: SettlementSimulator, queue
):

    async for jmsg in websocket:
        try:
            logger.info(jmsg)
            req = SimulationRequest.from_json(jmsg)
            solution = req.solution.to_json()

            logger.debug(jmsg)
            task = asyncio.create_task(
                simulate_and_respond(
                    simulator, solution, queue, req.estimate_block
                )
            )
            all_tasks.append(task)

        except Exception as e:
            logger.exception(f"Exception in rcv_msg: {e}")


async def send_msg(websocket, queue):
    try:
        while True:
            msg = await queue.get()
            try:
                logger.info(f"Sending msg: {msg.to_json()}")
            except:
                logging.exception("Problem")
            await websocket.send(msg.to_json())
    except websockets.ConnectionClosedOK:
        return


async def handler(websocket: WebSocketServerProtocol, path: str):

    sockets.add(websocket)
    queue = asyncio.Queue()
    simulator = SettlementSimulator()

    try:
        tasks = [
            asyncio.create_task(rcv_msg(websocket, simulator, queue)),
            asyncio.create_task(send_msg(websocket, queue)),
        ]
        await asyncio.wait(tasks)

    except websockets.ConnectionClosedOK:
        logger.info(f"Connection closed {websocket}.")
    finally:
        sockets.remove(websocket)


async def main(port=8001):
    async with websockets.server.serve(
        handler, "", port, ping_interval=10, ping_timeout=20
    ):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    parser = argparse.ArgumentParser("simple_example")
    parser.add_argument(
        "--port", help="Port to run on.", type=int, default=8001
    )
    args = parser.parse_args()


    asyncio.run(main(args.port))
