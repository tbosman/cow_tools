from models.batch_auction_model import AMMModel, BatchAuction, Order

# from models.WeightedMath import WeightedMath
from decimal import *
from typing import List
import math
from models.balancer_util import *
import functools
import operator
import scipy.optimize


def stable_equation(amplification_parameter, balances: list):
    # /**********************************************************************************************
    # // invariant                                                                                 //
    # // D = invariant                                                  D^(n+1)                    //
    # // A = amplification coefficient      A  n^n S + D = A D n^n + -----------                   //
    # // S = sum of balances                                             n^n P                     //
    # // P = product of balances                                                                   //
    # // n = number of tokens                                                                      //

    A = float(amplification_parameter)
    n = float(len(balances))
    S = float(sum(balances))
    P = float(functools.reduce(operator.mul, balances))

    return lambda D: A * n**n * S + D - A*D*n**n + (D**(n+1))/(n**n * P)



def stable_balance_given_invariant_all_others(amplification_parameter, balances: list, tokenIndexOut, invariant):
    # /**********************************************************************************************
    # // invariant                                                                                 //
    # // D = invariant                                                  D^(n+1)                    //
    # // A = amplification coefficient      A  n^n S + D = A D n^n + -----------                   //
    # // S = sum of balances                                             n^n P                     //
    # // P = product of balances                                                                   //
    # // n = number of tokens                                                                      //
    D = float(invariant)
    A = float(amplification_parameter)
    n = float(len(balances))
    other_balances = [b for i,b in enumerate(balances) if i != tokenIndexOut]
    Soth = float(sum(other_balances))
    Poth = float(functools.reduce(operator.mul, other_balances))

    return lambda b_out: A * n**n * (Soth + b_out) + D - A*D*n**n + (D**(n+1))/(n**n * (Poth * b_out))

def stable_calc_invariant_2(amplification_parameter, balances: list):
    eq = stable_equation(1300, balances)
    sol = scipy.optimize.root(eq, float(sum(balances)))

    return Decimal(sol.x[0])


def stable_calc_invariant(amplication_parameter, balances: list) -> Decimal:
    # /**********************************************************************************************
    # // invariant                                                                                 //
    # // D = invariant                                                  D^(n+1)                    //
    # // A = amplification coefficient      A  n^n S + D = A D n^n + -----------                   //
    # // S = sum of balances                                             n^n P                     //
    # // P = product of balances                                                                   //
    # // n = number of tokens                                                                      //
    # *********x************************************************************************************/
    amplication_parameter = Decimal(amplication_parameter)
    balances = [Decimal(b) for b in balances]

    bal_sum = 0
    for bal in balances:
        bal_sum += bal
    num_tokens = len(balances)
    if bal_sum == 0:
        return 0
    prevInvariant = 0
    invariant = bal_sum
    ampTimesTotal = amplication_parameter * num_tokens
    for i in range(255):
        print(invariant)
        P_D = num_tokens * balances[0]
        for j in range(1, num_tokens):
            P_D = math.ceil(((P_D * balances[j]) * num_tokens) / invariant)
        prevInvariant = invariant

        invariant = math.ceil(
            (
                (num_tokens * invariant) * invariant
                + (ampTimesTotal * bal_sum) * P_D
            )
            / ((num_tokens + 1) * invariant + (ampTimesTotal - 1) * P_D)
        )
        if invariant > prevInvariant:
            if invariant - prevInvariant <= 1:
                break
        elif prevInvariant - invariant <= 1:
            break

    return Decimal(invariant)


def getTokenBalanceGivenInvariantAndAllOtherBalances(
    amplificationParameter: Decimal,
    balances: List[Decimal],
    invariant: Decimal,
    tokenIndex: int,
) -> Decimal:
    getcontext().prec = 28
    ampTimesTotal = amplificationParameter * len(balances)
    bal_sum = Decimal(sum(balances))
    P_D = len(balances) * balances[0]
    for i in range(1, len(balances)):
        P_D = (P_D * balances[i] * len(balances)) / invariant

    bal_sum -= balances[tokenIndex]

    c = invariant * invariant / ampTimesTotal
    c = divUp(mulUp(c, balances[tokenIndex]), P_D)
    b = bal_sum + divDown(invariant, ampTimesTotal)
    prevTokenbalance = 0
    tokenBalance = divUp((invariant * invariant + c), (invariant + b))
    for i in range(255):
        prevTokenbalance = tokenBalance
        tokenBalance = divUp(
            (mulUp(tokenBalance, tokenBalance) + c),
            ((tokenBalance * Decimal(2)) + b - invariant),
        )
        if tokenBalance > prevTokenbalance:
            if tokenBalance - prevTokenbalance <= 1 / 1e18:
                break
        elif prevTokenbalance - tokenBalance <= 1 / 1e18:
            break
    return tokenBalance


def stable_calc_out_given_in(
    amplification_parameter,
    balances,
    tokenIndexIn,
    tokenAmountIn,
    tokenIndexOut,
):
    invariant = stable_calc_invariant_2(amplification_parameter, balances)

    balances[tokenIndexIn] = balances[tokenIndexIn] + tokenAmountIn
    eq = stable_balance_given_invariant_all_others(1300, balances, tokenIndexOut, invariant)
    sol = scipy.optimize.root(eq, float(sum(balances)))
    balances[tokenIndexIn] = balances[tokenIndexIn] - tokenAmountIn

    finalBalanceOut = Decimal(sol.x[0])
    result = balances[tokenIndexOut] - finalBalanceOut
    return result
    #
    # balances[tokenIndexIn] = balances[tokenIndexIn] + tokenAmountIn
    #
    # finalBalanceOut = getTokenBalanceGivenInvariantAndAllOtherBalances(
    #     amplification_parameter, balances, invariant, tokenIndexOut
    # )
    #
    # balances[tokenIndexIn] = balances[tokenIndexIn] - tokenAmountIn
    #
    # result = balances[tokenIndexOut] - finalBalanceOut
    # # result = finalBalanceOut - balances[tokenIndexOut]
    #
    # return result
    #

def weighted_calc_out_given_in(Bi, Bo, Wi, Wo, Ai_raw, fee):
    Ai = Ai_raw * (1 - fee)
    # return int(WeightedMath.calc_out_given_in(balance_in=Bi,
    #                                weight_in=Wi,
    #                                balance_out=Bo,
    #                                weight_out=Wo,
    #                                amount_in=Ai))
    Ao = Bo * (1 - (Bi / (Bi + Ai)) ** (Wi / Wo))
    return Ao


def weighted_calc_in_given_out(Bi, Bo, Wi, Wo, Ao, fee):
    Ai = Bi * ((Bo / (Bo - Ao)) ** (Wo / Wi) - 1)
    if Ai < 0:
        return 0
    Ai_raw = Ai / (1 - fee)
    return Ai_raw


class AMMLogic:
    def __init__(self, amm: AMMModel):
        self.amm = amm
        self.tokens = [t for t in amm.reserves]
        self.kind = amm.kind
        if self.kind in ["ConstantProduct", "Stable"]:
            self.balances = {t: int(float(v)) for t, v in amm.reserves.items()}
            self.weight = {t: 1 for t in self.tokens}
            if self.kind == "Stable":
                self.scaling_rates = {
                    t: int(v) for t, v in amm.scaling_rates.items()
                }
                self.amplification_parameter = int(amm.amplification_parameter)
        elif self.kind == "WeightedProduct":
            self.balances = {
                t: int(v["balance"]) for t, v in amm.reserves.items()
            }
            self.weight = {
                t: float(v["weight"]) for t, v in amm.reserves.items()
            }
        self.fee = float(amm.fee)

    def _get_params(self, intoken, outtoken):
        Bi = self.balances[intoken]
        Bo = self.balances[outtoken]
        Wi = self.weight[intoken]
        Wo = self.weight[outtoken]
        return Bi, Bo, Wi, Wo

    def calc_out_given_in(self, intoken, outtoken, inamount):
        Bi, Bo, Wi, Wo = self._get_params(intoken, outtoken)
        Ai = inamount

        if self.kind == "Stable":
            balances = [Decimal(self.balances[t]/self.scaling_rates[t]) for t in self.tokens]
            intoken_index = list(self.balances.keys()).index(intoken)
            outtoken_index = list(self.balances.keys()).index(outtoken)
            Ao = stable_calc_out_given_in(
                amplification_parameter=self.amplification_parameter,
                balances=balances,
                tokenIndexIn=intoken_index,
                tokenIndexOut=outtoken_index,
                tokenAmountIn=Decimal(Ai * (1 - self.fee)/self.scaling_rates[intoken]),
            )
            Ao =  int(Ao*self.scaling_rates[outtoken])
        else:
            Ao = weighted_calc_out_given_in(Bi, Bo, Wi, Wo, Ai, self.fee)

        # if self.amm.kind == "WeightedProduct":
        #     # see limitations
        #     # https://balancer.gitbook.io/balancer/core-concepts/protocol/limitations
        Ao = min(Bo * 0.3, Ao)

        return Ao

    def calc_in_given_out(self, intoken, outtoken, outamount):
        if self.kind == "Stable":
            raise NotImplemented()
        Bi, Bo, Wi, Wo = self._get_params(intoken, outtoken)
        Ao = outamount
        return weighted_calc_in_given_out(Bi, Bo, Wi, Wo, Ao, self.fee)

    def check_in_out_is_valid(
        self,
        intoken: str,
        outtoken: str,
        inamount: int,
        outamount: int,
        tol_pos=10**-5,
        tol_neg=10**-2,
    ):
        Bi, Bo, Wi, Wo = self._get_params(intoken, outtoken)
        Bon = Bo - outamount
        Bin = Bi + inamount * (1 - self.fee)

        is_valid = (
            (Bo**Wo * Bi**Wi) * (1 - tol_pos)
            < (Bon**Wo * Bin**Wi)
            < (Bo**Wo * Bi**Wi) * (1 + tol_neg)
        )
        k = (Bo**Wo) * (Bi**Wi)
        kn = (Bon**Wo) * (Bin**Wi)
        if not is_valid:
            print(f"k/kn: {k / kn}")
        return is_valid

    def get_spot_price(self, intoken, outtoken, swapfee=False):
        Bi, Bo, Wi, Wo = self._get_params(intoken, outtoken)
        swapmult = 1 / (1 - self.fee) if swapfee else 1
        return (Bi / Wi) / (Bo / Wo) * swapmult
