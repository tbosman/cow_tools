from cow_tools.models.batch_auction_model import TokenAmount

def token_transfer_to_inputs_outputs(token_transfer, lower_case=True):
    def tt(t):
        return t.lower() if lower_case else t
    inputs = [TokenAmount(amount=-a, token=tt(t)) for t,a in
              token_transfer.items() if a < 0]

    outputs = [TokenAmount(amount=a, token=tt(t)) for t,a in
               token_transfer.items() if a > 0]
    return inputs, outputs

