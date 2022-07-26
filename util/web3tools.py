import json
from web3 import Web3
import requests
import logging
from eth_typing import URI
from web3._utils.request import _get_session
from web3.providers.rpc import HTTPProvider
from web3 import AsyncHTTPProvider
from web3.types import Middleware, RPCEndpoint, RPCResponse
from requests_auth_aws_sigv4 import AWSSigV4
from typing import Any
import os



from cow_tools.models.batch_auction_model import ApprovalModel

with open(os.path.expanduser('~') +"/git_tree/cow_tools/config/apikeys.json", "r") as f:
    apikeys = json.load(f)

INFURA_KEY = apikeys["infura"]
infura_url = f"https://mainnet.infura.io/v3/{INFURA_KEY}"
adapter = requests.adapters.HTTPAdapter(pool_connections=500, pool_maxsize=500)
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)


logging.getLogger("requests_auth_aws_sigv4").setLevel("INFO")
logging.getLogger("websockets").setLevel("INFO")
aws_auth = AWSSigV4(
    "managedblockchain",
    aws_access_key_id=apikeys["AWS_access_key_id"],
    aws_secret_access_key=apikeys["AWS_secret_access_key_id"],
    region=apikeys["AWS_region"],  # us-east-1
)


def make_post_request(
    endpoint_uri: URI, data: bytes, *args: Any, **kwargs: Any
) -> bytes:
    kwargs.setdefault("timeout", 10)
    session = _get_session(endpoint_uri)
    # https://github.com/python/mypy/issues/2582
    response = session.post(
        endpoint_uri, data=data, *args, **kwargs, auth=aws_auth
    )  # type: ignore
    response.raise_for_status()

    return response.content


class AMBHTTPProvider(HTTPProvider):
    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        # self.logger.debug("Making request HTTP. URI: %s, Method: %s",
        #                   self.endpoint_uri, method)

        # .decode() since the AWS sig library expects a string.
        request_data = self.encode_rpc_request(method, params).decode()
        raw_response = make_post_request(
            self.endpoint_uri, request_data, **self.get_request_kwargs()
        )
        response = self.decode_rpc_response(raw_response)
        # self.logger.debug("Getting response HTTP. URI: %s, "
        #                   "Method: %s, Response: %s",
        #                   self.endpoint_uri, method, response)
        return response


# web3 = Web3(Web3.HTTPProvider(apikeys['quicknode_http'], session=session))
web3 = Web3(Web3.HTTPProvider(apikeys["eth_plm"], session=session))
aweb3 = Web3(Web3.AsyncHTTPProvider(apikeys["eth_plm"]))
infuraweb3 = Web3(Web3.HTTPProvider(infura_url, session=session))
# web3 = Web3(Web3.WebsocketProvider(apikeys['quicknode_ws'])) #, session=session))
# web3 = Web3(AMBHTTPProvider(apikeys["AWS_http_endpoint"], session=session))
# web3 = Web3(AMBHTTPProvider(apikeys["AWS_http_endpoint"], session=session))
# web3 = Web3(Web3.HTTPProvider(apikeys['ethereum_node']))
# web3 = Web3(Web3.HTTPProvider(apikeys['ethereum_node']))


#
# async_provider = AMBWebsocketProvider(
#     endpoint_uri=apikeys[ 'AWS_ws_endpoint' ],
#     websocket_kwargs=dict(
#         create_protocol=handle_create_protocol
#     )
# )
#
# web3 = Web3(async_provider)
#


def get_abi(contract_address, force_download=False):
    contract_address = Web3.toChecksumAddress(contract_address)
    this_path = os.path.dirname(__file__)
    local_json = os.path.abspath(f"{this_path}/../contracts/etherscan/{contract_address}.json")
    try:
        assert not force_download, "Forcing download of ABI"
        with open(local_json) as f:
            abi = json.load(f)
            return abi
    except FileNotFoundError as e:
        logging.info("Contract not seen before, downloading from Etherscan")
    except AssertionError as e:
        logging.info(e)
    ETHERSCAN_KEY = apikeys["etherscan"]
    # https://medium.com/coinmonks/discovering-the-secrets-of-an-ethereum-transaction-64febb00935c
    abi_endpoint = (
        f"https://api.etherscan.io/api?"
        f"module=contract&action=getabi&address={contract_address}&apikey={ETHERSCAN_KEY}"
    )
    abi = json.loads(requests.get(abi_endpoint).text)["result"]
    with open(local_json, "w") as f:
        json.dump(abi, f)
    return abi


def get_contract(address, force_download=False, web3=web3):
    abi = get_abi(address, force_download=force_download)
    return web3.eth.contract(
        address=Web3.toChecksumAddress(address),
        abi=abi,
    )



def get_ERC20_contract(address):
    abi = json.loads(open("contracts/artifacts/ERC20.json", "r").read())["abi"]
    return web3.eth.contract(address=Web3.toChecksumAddress(address), abi=abi)


def hexstr2Bytes(hexstr):
    byte_array = web3.toBytes(hexstr=hexstr)
    return [b for b in byte_array]


class ApprovalGenerator:
    def __init__(
        self,
        # gas_price,
        from_address="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
    ):
        # self.gas_price = gas_price
        self.from_address = from_address

    def get_allowance(self, spender, token):
        return (
            get_ERC20_contract(token)
            .functions.allowance(self.from_address, spender)
            .call()
        )

    def get_approval(self, spender, token, amount):
        return (
            get_ERC20_contract(token)
            .functions.approve(spender, amount)
            .buildTransaction({"gasPrice": 0, "gas": 50000})
        )

    def get_all_approvals(self, wrapped_interactions: list):
        total_amount_for_token_spender = {}
        for i, w in wrapped_interactions.items():
            key = (
                Web3.toChecksumAddress(w.interaction.target),
                Web3.toChecksumAddress(w.execution.buy_token),
            )
            total_amount_for_token_spender[key] = (
                total_amount_for_token_spender.get(key, 0)
                + w.execution.exec_buy_amount
            )

        approvals = []
        for (spender, token), amount in total_amount_for_token_spender.items():
            allowance = self.get_allowance(spender, token)
            if allowance < amount:
                logging.info(
                    f"Allowance ({allowance}) insufficient to cover amount ({amount})"
                )
                approvals.append(
                    ApprovalModel(token, spender, int(2**256 - 1))
                )
        return approvals

#
# gen = ApprovalGenerator()
# WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
# DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
# USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
# WBTC = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
# USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
#
#
# def get_and_print_approval(token, amount):
#     approval = gen.get_approval(
#         spender="0xE592427A0AEce92De3Edee1F18E0157C05861564",
#         token=token,
#         amount=amount,
#     )
#     print(f"Approval to spend {amount} of token: {token}. ")
#     print({k: v for k, v in approval.items() if k in ["to", "data"]})
#
#
# get_and_print_approval(token=WETH, amount=int(10**18 * (10**7 / 2000)))
# get_and_print_approval(token=DAI, amount=int(10**6 * (10**7)))
# get_and_print_approval(token=USDC, amount=int(10**18 * (10**7)))
# get_and_print_approval(token=USDT, amount=int(10**6 * (10**7)))
# get_and_print_approval(token=WBTC, amount=int(10**8 * (10**7 / 25000)))
#
#
# gen.get_approval(spender="0xE592427A0AEce92De3Edee1F18E0157C05861564", token=WETH, amount=int(10**18* (10**7/2000) ))
# gen.get_approval(spender="0xE592427A0AEce92De3Edee1F18E0157C05861564", token=DAI, amount=int(10**6* (10**7) ))
# gen.get_approval(spender="0xE592427A0AEce92De3Edee1F18E0157C05861564", token=USDC, amount=int(10**18* (10**7) ))
# gen.get_approval(spender="0xE592427A0AEce92De3Edee1F18E0157C05861564", token=USDT, amount=int(10**6* (10**7) ))
# gen.get_approval(spender="0xE592427A0AEce92De3Edee1F18E0157C05861564", token=WBTC, amount=int(10**8* (10**7/25000) ))


#
#
# def generate_approval(from_token, fromAddress, to_address, sell_amount):
#     try:
#         # from_token_contract = get_erc20_contract(from_token)
#         # allowance = from_token_contract.functions.allowance(
#         #     fromAddress, to_address
#         # ).call()
#         if allowance < sell_amount:
#             logging.info(
#                 f"Allowance: {allowance} insufficient to cover trade: {sell_amount}")
#             approval = from_token_contract.functions.approve(
#                 to_address, int(10 * sell_amount)
#             ).buildTransaction({"gasPrice": self.gasPrice, "gas": 10 ** 7})
#
#             tx['needs_approval'] = True
#             tx['approval'] = approval
#         else:
#             swap['needs_approval'] = False
#
#     except Exception as e:
#         logging.info(f'Allowance for {from_token}.  Exception {e}')
#
