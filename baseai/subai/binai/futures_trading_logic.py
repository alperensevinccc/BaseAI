# Futures Trading Logic Module for BinAI

import numpy as np

def analyze_market_data(data):
    # Analyze the provided market data
    trends = {'uptrend': False, 'downtrend': False, 'stable': True}
    price_changes = np.array(data['price_changes'])
    avg_change = np.mean(price_changes)
    std_dev = np.std(price_changes)
    if avg_change > 0.05 and std_dev < 0.02:
        trends['uptrend'] = True
        trends['stable'] = False
    elif avg_change < -0.05 and std_dev < 0.02:
        trends['downtrend'] = True
        trends['stable'] = False
    return trends

def decide_trade_action(market_trends):
    # Decide on the trading action based on market trends
    if market_trends['uptrend']:
        return 'buy'
    elif market_trends['downtrend']:
        return 'sell'
    else:
        return 'hold'

def main(data):
    # Main function to execute trading logic
    market_trends = analyze_market_data(data)
    action = decide_trade_action(market_trends)
    return action

if __name__ == '__main__':
    sample_data = {'price_changes': [0.04, 0.06, 0.07, -0.02, 0.01]}
    result = main(sample_data)
    print(f'Trade action: {result}')