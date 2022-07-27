from dataclasses import dataclass
from enum import Enum

from dataclasses_json import dataclass_json
from typing import Dict, Optional, List, Union, Iterable
import logging
from collections import defaultdict


def str_field_to_int(obj, field):
    subobj = getattr(obj, field)
    setattr(obj, field, int(subobj))


def int_field_to_str(obj, field):
    subobj = getattr(obj, field)
    setattr(obj, field, str(int(subobj)))


def str_field_to_float(obj, field):
    subobj = getattr(obj, field)
    if subobj is not None:
        setattr(obj, field, float(subobj))


def float_field_to_str(obj, field):
    subobj = getattr(obj, field)
    if subobj is not None:
        setattr(obj, field, f"{(float(subobj)):f}")


class StrNumClass:
    def __init__(self):
        self._strint_fields = []
        self._strfloat_fields = []
        self._strnumclass_fields = []
        self._strdict_fields = []

    def strint_to_num(self):
        for f in self._strint_fields:
            str_field_to_int(self, f)
        for f in self._strfloat_fields:
            str_field_to_float(self, f)
        for f in self._strnumclass_fields:
            self.__getattribute__(f).strint_to_num()
        for f in self._strdict_fields:
            for v in self.__getattribute__(f).values():
                v.strint_to_num()

    def strint_to_str(self):
        for f in self._strint_fields:
            int_field_to_str(self, f)
        for f in self._strfloat_fields:
            float_field_to_str(self, f)
        for f in self._strnumclass_fields:
            self.__getattribute__(f).strint_to_str()
        for f in self._strdict_fields:
            for v in self.__getattribute__(f).values():
                v.strint_to_str()


# def hexstr2Bytes(hexstr):
#     return hexstr
#     # from web3 import Web3
#     # http = "https://staging-openethereum.mainnet.gnosisdev.com"
#     # w3 = Web3(Web3.HTTPProvider(http))
#     # byte_array = w3.toBytes(hexstr=hexstr)
#     # return [b for b in byte_array]
    #
@dataclass_json
@dataclass
class Token(StrNumClass):
    alias: str
    decimals: int
    normalize_priority: int
    internal_buffer: Optional[int] = None
    external_price: Optional[float] = None

    def __post_init__(self):
        super().__init__()
        self._strfloat_fields.extend(["external_price"])



@dataclass_json
@dataclass
class TokenAmount(StrNumClass):
    amount: int
    token: str

    def __post_init__(self):
        super().__init__()
        self._strint_fields.extend(["amount"])

# @dataclass_json
# @dataclass
class InternalExecutionPlan(Enum):
    INTERNAL = 'internal'


@dataclass_json
@dataclass
class ApprovalModel(StrNumClass):
    token: str
    spender: str
    amount: int

    def __post_init__(self):
        super().__init__()
        self._strint_fields.extend(["amount"])



@dataclass_json
@dataclass
class ExecutionPlanCoordinatesModel:
    position: int
    sequence: int


@dataclass_json
@dataclass
class InteractionData(StrNumClass):
    target: str
    call_data: str
    value: Optional[int] = 0
    inputs: Optional[List[TokenAmount]] = None
    outputs: Optional[List[TokenAmount]] = None
    exec_plan: Optional[Union[ExecutionPlanCoordinatesModel, InternalExecutionPlan]] = None


    def __post_init__(self):
        super().__init__()
        self._strint_fields.extend(["value"])

    def __hash__(self):
        return hash(self.to_json())


    def strint_to_str(self):
        super().strint_to_str()
        if hasattr(self, 'inputs'):
            if self.inputs: # TODO Remove
                for ta in self.inputs:
                    ta.strint_to_str()
        if hasattr(self, 'outputs'):
            if self.outputs:
                for ta in self.outputs:
                    ta.strint_to_str()




class Execution:
    sell_token: str
    buy_token: str
    exec_sell_amount: int
    exec_buy_amount: int

    def executed_price(self):
        return self.exec_sell_amount / self.exec_buy_amount

    def scaled_executed_price(self, reference_prices):
        price = (
            self.executed_price()
            * reference_prices[self.sell_token]
            / reference_prices[self.buy_token]
        )
        return price

    def partial_execution(self, frac):
        new_execution = self.__copy__()
        new_execution.exec_sell_amount = new_execution.exec_sell_amount * frac
        new_execution.exec_buy_amount = new_execution.exec_buy_amount * frac
        return new_execution

    def merge(self, other):
        assert (
            self.sell_token == other.sell_token
            and self.buy_token == other.buy_token
        )
        new_execution = self.__copy__()
        new_execution.exec_sell_amount += other.exec_sell_amount
        new_execution.exec_buy_amount += other.exec_buy_amount
        return new_execution

    def __copy__(self):
        return type(self)(**self.to_dict())

def get_net_flow(executions: Iterable[Execution]):
    net_flow = defaultdict(lambda: 0)
    for e in executions:
        net_flow[e.sell_token] += e.exec_sell_amount
        net_flow[e.buy_token] -= e.exec_buy_amount
    return net_flow



@dataclass_json
@dataclass
class AMMExecution(StrNumClass, Execution):
    sell_token: str
    buy_token: str
    exec_sell_amount: str
    exec_buy_amount: str
    exec_plan: Optional[Union[ExecutionPlanCoordinatesModel, InternalExecutionPlan]] = ExecutionPlanCoordinatesModel(0, 1)

    def __post_init__(self):
        super().__init__()
        self._strint_fields.extend(["exec_sell_amount", "exec_buy_amount"])

    def __copy__(self):
        return AMMExecution(**self.to_dict())

    def __hash__(self):
        return hash(
            str(self.sell_token)
            + str(self.buy_token)
            + str(int(self.exec_sell_amount))
            + str(int(self.exec_buy_amount))
        )


@dataclass_json
@dataclass
class AMMModel(StrNumClass):
    kind: str
    fee: float
    cost: TokenAmount
    mandatory: bool
    reserves: Dict
    scaling_rates: Optional[Dict] = None
    amplification_parameter: Optional[int] = None
    execution: Optional[List[AMMExecution]] = None

    def __post_init__(self):
        super().__init__()
        self._strfloat_fields.extend(["fee"])
        self._strnumclass_fields.extend(["cost"])

    def strint_to_num(self):
        super().strint_to_num()
        if self.execution:
            for e in self.execution:
                e.strint_to_num()

    def strint_to_str(self):
        super().strint_to_str()
        if self.execution:
            for e in self.execution:
                e.strint_to_str()


#
#
# @dataclass_json
# @dataclass
# class ExecutedAMMModel:
#     kind: str
#     fee: float
#     cost: Cost
#     mandatory: bool
#     reserves: Dict
#     sell_token: str
#     buy_token: str
#     execution: AMMExecution =
#
#     exec_sell_amount: str
#     exec_buy_amount: str
#


@dataclass_json
@dataclass
class Order(StrNumClass):
    sell_token: str
    buy_token: str
    sell_amount: Union[int, str]
    buy_amount: Union[int, str]
    allow_partial_fill: bool
    is_sell_order: bool
    fee: TokenAmount
    cost: TokenAmount
    is_liquidity_order: bool
    has_atomic_execution: Optional[bool] = False

    def __post_init__(self):
        super().__init__()
        self._strint_fields.extend(["sell_amount", "buy_amount"])
        self._strnumclass_fields.extend(["fee", "cost"])

    def limit_price(self):
        return int(self.sell_amount) / int(self.buy_amount)

    def scaled_limit_price(self, reference_prices):
        return (
            self.limit_price()
            * reference_prices[self.sell_token]
            / reference_prices[self.buy_token]
        )

    def type_tag(self):
        tag = ""
        if self.is_sell_order:
            tag += "[S]"
        else:
            tag += "[B]"
        if self.is_liquidity_order:
            tag += "[L]"
        if self.allow_partial_fill:
            tag += "[P]"
        if self.has_atomic_execution:
            tag += "[A]"
        return tag


    def __hash__(self):
        return hash(self.to_json())


@dataclass_json
@dataclass
class BatchAuction(StrNumClass):
    tokens: Dict[str, Token]
    orders: Dict[int, Order]
    amms: Dict[int, AMMModel]
    metadata: dict
    instance_name: Optional[str] = "No name provided"

    def __post_init__(self):
        super().__init__()
        self._strdict_fields.extend(["tokens", "orders", "amms"])


@dataclass_json
@dataclass
class ExecutedOrder(Order, Execution):
    exec_sell_amount: Union[int, str] = 0
    exec_buy_amount: Union[int, str] = 0
    exec_plan: Optional[Union[ExecutionPlanCoordinatesModel, InternalExecutionPlan]] = None

    def from_order(order: Order, exec_sell_amount: int, exec_buy_amount: int):
        return ExecutedOrder(
            buy_token=order.buy_token,
            buy_amount=order.buy_amount,
            sell_token=order.sell_token,
            sell_amount=order.sell_amount,
            allow_partial_fill=order.allow_partial_fill,
            is_sell_order=order.is_sell_order,
            fee=order.fee,
            cost=order.cost,
            is_liquidity_order=order.is_liquidity_order,
            exec_sell_amount=exec_sell_amount,
            exec_buy_amount=exec_buy_amount,
        )

    def __post_init__(self):
        super().__post_init__()
        self._strint_fields.extend(["exec_buy_amount", "exec_sell_amount"])

    def __hash__(self):
        return hash(
            str(self.sell_token)
            + str(self.buy_token)
            + str(int(self.exec_sell_amount))
            + str(int(self.exec_buy_amount))
        )

    # def executed_price(self):
    #     return self.exec_sell_amount / self.exec_buy_amount
    # def __hash__(self):
    #     return hash(
    #         str(self.sell_token)
    #         + str(self.buy_token)
    #         + str(int(self.exec_sell_amount))
    #         + str(int(self.exec_buy_amount))
    #     )
    #
    # def __copy__(self):
    #     return ExecutedOrder(**self.to_dict())
    #
    # def partial_execution(self, frac):
    #     new_execution = self.__copy__()
    #     new_execution.exec_sell_amount = new_execution.exec_sell_amount * frac
    #     new_execution.exec_buy_amount = new_execution.exec_buy_amount * frac
    #     return new_execution
    #
    # def merge(self, other):
    #     assert (
    #         self.sell_token == other.sell_token
    #         and self.buy_token == other.buy_token
    #     )
    #     new_execution = self.__copy__()
    #     new_execution.exec_sell_amount += other.exec_sell_amount
    #     new_execution.exec_buy_amount += other.exec_buy_amount
    #     return new_execution
    #


@dataclass_json
@dataclass
class SettledBatchAuction(StrNumClass):
    orders: Dict[int, ExecutedOrder]
    amms: Dict[int, AMMModel]
    prices: Dict[str, str]
    approvals: Optional[List[ApprovalModel]] = ""
    ref_token: Optional[str] = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    interaction_data: Optional[List[InteractionData]] = ""

    def __post_init__(self):
        super().__init__()
        # self.prices = {
        #     k: str(int(p)) for k, p in self.prices.items()
        # }  # TODO fold into StrNumClass
        self._strdict_fields.extend(["orders", "amms"])


    def strint_to_str(self):
        super().strint_to_str()
        for id in self.interaction_data:
            id.strint_to_str()
        for appr in self.approvals:
            appr.strint_to_str()
        for t in self.prices:
            self.prices[t] = str(self.prices[t])


    def strint_to_num(self):
        super().strint_to_num()
        for id in self.interaction_data:
            id.strint_to_num()
        for appr in self.approvals:
            appr.strint_to_num()
        for t in self.prices:
            self.prices[t] = int(self.prices[t])
