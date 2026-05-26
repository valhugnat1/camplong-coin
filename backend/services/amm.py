"""
services/amm.py - Math AMM x*y=k (Uniswap v1 simplifie).

Reserves stockees en entiers :
  - reserve_camp en CAMP entiers
  - reserve_milk en milli-bouteilles (1 bouteille = 1000)

Convention "fee on the input" : on prend les frais sur le montant entrant
(CAMP pour un buy, milk pour un sell), les frais restent dans le pool donc
augmentent doucement k au fil du temps - effet "yield" pour le LP (ici la
treasury / admin).

Tous les helpers retournent un dict serialisable (utile pour preview cote
front via GET /milk/pools/{symbol}/quote).
"""
from typing import TypedDict


class Quote(TypedDict):
    side: str
    amount_in: int
    amount_out: int
    fee: int
    price_before: float
    price_after: float
    new_reserve_camp: int
    new_reserve_milk: int


def current_price(reserve_camp: int, reserve_milk: int) -> float:
    """
    Prix marginal d'une bouteille en CAMP.
    reserve_milk est en milli-bouteilles, donc on multiplie par 1000 pour
    sortir un prix "CAMP par bouteille".
    """
    if reserve_milk <= 0:
        return 0.0
    return reserve_camp * 1000.0 / reserve_milk


def buy_quote(reserve_camp: int, reserve_milk: int, fee_pct: float,
              camp_in: int) -> Quote:
    """
    Combien de milli-bouteilles je recois pour `camp_in` CAMP.
    fee_pct est en pourcent (0.5 = 0.5%).
    """
    if camp_in <= 0:
        raise ValueError("camp_in doit etre > 0")
    if reserve_camp <= 0 or reserve_milk <= 0:
        raise ValueError("Reserves invalides")

    fee = int(camp_in * fee_pct / 100)
    camp_in_net = camp_in - fee
    if camp_in_net <= 0:
        raise ValueError("Montant trop faible apres frais")

    k = reserve_camp * reserve_milk
    new_reserve_camp = reserve_camp + camp_in_net
    # Floor div - le pool garde la poussiere.
    new_reserve_milk = k // new_reserve_camp
    milk_out = reserve_milk - new_reserve_milk

    price_before = current_price(reserve_camp, reserve_milk)
    price_after = current_price(new_reserve_camp, new_reserve_milk)

    return {
        "side": "buy",
        "amount_in": camp_in,
        "amount_out": milk_out,
        "fee": fee,
        "price_before": price_before,
        "price_after": price_after,
        "new_reserve_camp": new_reserve_camp,
        "new_reserve_milk": new_reserve_milk,
    }


def sell_quote(reserve_camp: int, reserve_milk: int, fee_pct: float,
               milk_in: int) -> Quote:
    """
    Combien de CAMP je recois pour `milk_in` milli-bouteilles.
    Frais preleves sur le CAMP en sortie (apres calcul de la quote).
    """
    if milk_in <= 0:
        raise ValueError("milk_in doit etre > 0")
    if reserve_camp <= 0 or reserve_milk <= 0:
        raise ValueError("Reserves invalides")

    k = reserve_camp * reserve_milk
    new_reserve_milk = reserve_milk + milk_in
    new_reserve_camp = k // new_reserve_milk
    camp_out_gross = reserve_camp - new_reserve_camp
    fee = int(camp_out_gross * fee_pct / 100)
    camp_out = camp_out_gross - fee
    if camp_out < 0:
        camp_out = 0

    price_before = current_price(reserve_camp, reserve_milk)
    price_after = current_price(new_reserve_camp, new_reserve_milk)

    return {
        "side": "sell",
        "amount_in": milk_in,
        "amount_out": camp_out,
        "fee": fee,
        "price_before": price_before,
        "price_after": price_after,
        "new_reserve_camp": new_reserve_camp,
        "new_reserve_milk": new_reserve_milk,
    }
