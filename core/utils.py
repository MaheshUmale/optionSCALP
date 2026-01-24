import math

def norm_pdf(x):
    return (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x**2)

def norm_cdf(x):
    """Abramowitz and Stegun approximation for CDF of normal distribution."""
    if x < 0:
        return 1 - norm_cdf(-x)
    a1 = 0.319381530
    a2 = -0.356563782
    a3 = 1.781477937
    a4 = -1.821255978
    a5 = 1.330274429
    p = 0.2316419
    t = 1.0 / (1.0 + p * x)
    return 1.0 - norm_pdf(x) * (a1 * t + a2 * t**2 + a3 * t**3 + a4 * t**4 + a5 * t**5)

def black_scholes_greeks(S, K, T, r, sigma, option_type='CE'):
    """
    Calculate Black-Scholes greeks.
    S: current price
    K: strike price
    T: time to expiration (in years)
    r: risk-free rate (e.g. 0.07 for 7%)
    sigma: implied volatility (e.g. 0.20 for 20%)
    """
    if T <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == 'CE':
        delta = norm_cdf(d1)
        theta = -(S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))) - r * K * math.exp(-r * T) * norm_cdf(d2)
    else:
        delta = norm_cdf(d1) - 1
        theta = -(S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))) + r * K * math.exp(-r * T) * norm_cdf(-d2)

    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * norm_pdf(d1) * math.sqrt(T)
    rho = K * T * math.exp(-r * T) * norm_cdf(d2 if option_type == 'CE' else -d2)
    if option_type == 'PE': rho = -rho

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 4),
        "theta": round(theta / 365, 4), # Daily theta
        "vega": round(vega / 100, 4), # Per 1% change in sigma
        "rho": round(rho / 100, 4)
    }

def black_scholes_price(S, K, T, r, sigma, option_type='CE'):
    if T <= 0: return max(0, S - K) if option_type == 'CE' else max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == 'CE':
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

def find_iv(market_price, S, K, T, r, option_type='CE'):
    """Find implied volatility using Newton-Raphson."""
    if T <= 0: return 0.2 # Fallback
    sigma = 0.3 # Initial guess
    for i in range(20):
        price = black_scholes_price(S, K, T, r, sigma, option_type)
        diff = price - market_price
        if abs(diff) < 0.01:
            return sigma
        # Vega for Newton-Raphson
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        vega = S * norm_pdf(d1) * math.sqrt(T)
        if vega < 0.0001: break
        sigma = sigma - diff / vega
        if sigma <= 0: sigma = 0.001
    return sigma

def calculate_buildup(price_change, oi_change):
    if price_change > 0 and oi_change > 0:
        return "Long Buildup"
    elif price_change < 0 and oi_change > 0:
        return "Short Buildup"
    elif price_change < 0 and oi_change < 0:
        return "Long Unwinding"
    elif price_change > 0 and oi_change < 0:
        return "Short Covering"
    return "Neutral"
