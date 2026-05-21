"""
email_service.py - Envoi d'emails transactionnels via SMTP.

Deux notifs :
  - send_admin_new_order : quand un user cree une demande d'achat ou de vente
  - send_user_order_done : quand l'admin marque une demande comme traitee

L'envoi se fait en best-effort : si SMTP echoue, on logge mais on ne raise pas.
Une demande ne doit pas etre bloquee par un email qui ne part pas.

A appeler via FastAPI BackgroundTasks pour ne pas bloquer la requete HTTP.
"""
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
    ADMIN_EMAIL, FRONTEND_URL
)

logger = logging.getLogger("camplong.email")


def _send(to: str, subject: str, body: str) -> bool:
    """Envoi SMTP brut. Retourne True si OK, False sinon (jamais de raise)."""
    if not SMTP_HOST or not SMTP_USER or not to:
        logger.warning(
            "SMTP non configure ou destinataire vide, email skip (to=%r, subject=%r)",
            to, subject
        )
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)

        logger.info("Email envoye a %s : %s", to, subject)
        return True
    except Exception:
        logger.exception("Echec d'envoi d'email a %s (subject=%r)", to, subject)
        return False


def send_admin_new_order(order: dict, user_email: Optional[str]) -> None:
    """Notifie l'admin qu'une nouvelle demande vient d'etre creee."""
    type_label = "ACHAT" if order["type"] == "buy" else "VENTE"
    email_str = user_email or "(pas d'email renseigne)"
    handle_str = order.get("handle", "")
    note_str = order.get("note", "")

    handle_block = f"  Handle    : {handle_str}\n" if handle_str else ""
    note_block   = f"  Note      : {note_str}\n"   if note_str else ""

    subject = (
        f"[CamplongCoin] Nouvelle demande {type_label} - "
        f"{order['username']} - {order['amount_camp']} CAMP / {order['amount_eur']:.2f} EUR"
    )

    body = (
        f"Nouvelle demande de {type_label.lower()} sur CamplongCoin :\n\n"
        f"  Order ID  : #{order['id']}\n"
        f"  User      : {order['username']}\n"
        f"  Email     : {email_str}\n"
        f"  Type      : {type_label}\n"
        f"  Montant   : {order['amount_camp']} CAMP\n"
        f"  Valeur    : {order['amount_eur']:.2f} EUR\n"
        f"{handle_block}{note_block}"
        f"  Cree le   : {order['ts']}\n\n"
        f"Traiter la demande dans le backoffice :\n"
        f"  {FRONTEND_URL}/admin/orders\n\n"
        f"--\n"
        f"CamplongCoin (notif auto)\n"
    )
    _send(ADMIN_EMAIL, subject, body)


def send_bet_arbiter_assigned(bet: dict, arbiter_email: str) -> None:
    """Previent un arbitre qu'il a ete designe pour trancher un pari."""
    subject = f"[CamplongCoin] On t'a designe arbitre - pari #{bet['id']}"
    body = (
        f"Salut,\n\n"
        f"{bet['creator_username']} t'a designe arbitre pour ce pari :\n\n"
        f"  \"{bet['statement']}\"\n\n"
        f"  Pari #{bet['id']}\n"
        f"  Mise creator   : {bet['stake_creator']} CAMP ({bet['creator_side'].upper()})\n"
        f"  Mise opponent  : {bet['stake_opponent']} CAMP\n"
        f"  Commission     : {bet['arbiter_fee_pct']}% du pot\n"
        f"  Deadline       : {bet['deadline']}\n\n"
        f"Tu pourras trancher quand un opposant aura matche le pari.\n\n"
        f"Voir le pari :\n  {FRONTEND_URL}/paris/{bet['id']}\n\n"
        f"--\nCamplongCoin (notif auto)\n"
    )
    _send(arbiter_email, subject, body)


def send_bet_matched(bet: dict, creator_email: str, matcher_username: str) -> None:
    """Previent le creator que quelqu'un a pris son pari."""
    subject = f"[CamplongCoin] {matcher_username} a pris ton pari #{bet['id']}"
    body = (
        f"Salut {bet['creator_username']},\n\n"
        f"{matcher_username} vient de prendre ton pari :\n\n"
        f"  \"{bet['statement']}\"\n\n"
        f"  Pot total   : {bet['stake_creator'] + bet['stake_opponent']} CAMP\n"
        f"  Ton cote    : {bet['creator_side'].upper()}\n"
        f"  Deadline    : {bet['deadline']}\n"
        f"  Arbitre     : {bet['arbiter_username'] or '(admin)'}\n\n"
        f"Voir le pari :\n  {FRONTEND_URL}/paris/{bet['id']}\n\n"
        f"--\nCamplongCoin (notif auto)\n"
    )
    _send(creator_email, subject, body)


def send_bet_resolved(bet: dict, user_email: str, username: str) -> None:
    """Notifie un participant qu'un pari a ete resolu."""
    res = bet["resolution"]
    pot = bet["stake_creator"] + bet["stake_opponent"]

    if res == "void":
        outcome = "Le pari a ete annule (void). Ta mise t'a ete remboursee."
    else:
        winner = (
            bet["creator_username"]
            if bet["creator_side"] == res
            else bet["opponent_username"]
        )
        if winner == username:
            outcome = (
                f"Tu as GAGNE ! Resolution: {res.upper()}, "
                f"pot {pot} CAMP, payout sur ton wallet."
            )
        else:
            outcome = (
                f"Tu as perdu. Resolution: {res.upper()}, "
                f"le pot ({pot} CAMP) est alle a {winner}."
            )

    subject = f"[CamplongCoin] Pari #{bet['id']} resolu"
    body = (
        f"Salut {username},\n\n"
        f"Le pari \"{bet['statement']}\" vient d'etre resolu par "
        f"{bet['resolved_by']}.\n\n"
        f"{outcome}\n\n"
        f"Voir le pari :\n  {FRONTEND_URL}/paris/{bet['id']}\n\n"
        f"--\nCamplongCoin (notif auto)\n"
    )
    _send(user_email, subject, body)


def send_user_order_done(order: dict, user_email: str) -> None:
    """Confirme au user que sa demande a ete traitee par l'admin."""
    type_label = "achat" if order["type"] == "buy" else "vente"

    if order["type"] == "buy":
        action_text = f"Tu as bien recu {order['amount_camp']} CAMP sur ton wallet."
    else:
        action_text = (
            f"Hugo a envoye {order['amount_eur']:.2f} EUR sur ton compte Wero/Revolut."
        )

    admin_note_block = ""
    if order.get("admin_note"):
        admin_note_block = f"\nMessage d'Hugo : {order['admin_note']}\n"

    subject = f"[CamplongCoin] Demande de {type_label} traitee"
    body = (
        f"Salut {order['username']},\n\n"
        f"Ta demande de {type_label} de {order['amount_camp']} CAMP "
        f"({order['amount_eur']:.2f} EUR) vient d'etre traitee par Hugo.\n\n"
        f"{action_text}\n"
        f"{admin_note_block}\n"
        f"Verifie ton solde sur :\n"
        f"  {FRONTEND_URL}/wallet\n\n"
        f"A bientot sur CamplongCoin.\n\n"
        f"--\n"
        f"L'equipe (i.e. Hugo)\n"
    )
    _send(user_email, subject, body)
