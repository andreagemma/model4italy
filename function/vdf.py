from numpy import pow

def bpr(**kw):
    return kw["t0"]*(1+kw.get("a",0.15)*pow(kw["q"]/kw["c"], kw.get("b",4)))