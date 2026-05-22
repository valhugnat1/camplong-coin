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
    opts = ", ".join(o["label"] for o in bet.get("options", []))
    subject = f"[CamplongCoin] On t'a designe arbitre - pari #{bet['id']}"
    body = (
        f"Salut,\n\n"
        f"{bet['creator_username']} t'a designe arbitre pour ce pari :\n\n"
        f"  \"{bet['statement']}\"\n\n"
        f"  Pari #{bet['id']}\n"
        f"  Mise unique : {bet['stake']} CAMP par participant\n"
        f"  Options     : {opts}\n"
        f"  Deadline    : {bet['deadline']}\n\n"
        f"Tu pourras trancher quand la deadline approche ou des qu'il y a\n"
        f"assez de participants pour rendre le verdict significatif.\n\n"
        f"Voir le pari :\n  {FRONTEND_URL}/paris/{bet['id']}\n\n"
        f"--\nCamplongCoin (notif auto)\n"
    )
    _send(arbiter_email, subject, body)


def send_bet_joined(bet: dict, creator_email: str, joiner_username: str,
                    option_label: str) -> None:
    """Previent le createur que quelqu'un vient de rejoindre son pari."""
    subject = f"[CamplongCoin] {joiner_username} a rejoint ton pari #{bet['id']}"
    body = (
        f"Salut {bet['creator_username']},\n\n"
        f"{joiner_username} vient de rejoindre ton pari sur l'option "
        f"\"{option_label}\" :\n\n"
        f"  \"{bet['statement']}\"\n\n"
        f"  Mise unique     : {bet['stake']} CAMP\n"
        f"  Participants    : {bet.get('participants_count', '?')}\n"
        f"  Pot total       : {bet.get('pot_total', '?')} CAMP\n"
        f"  Deadline        : {bet['deadline']}\n\n"
        f"Voir le pari :\n  {FRONTEND_URL}/paris/{bet['id']}\n\n"
        f"--\nCamplongCoin (notif auto)\n"
    )
    _send(creator_email, subject, body)


def send_bet_resolved(bet: dict, user_email: str, username: str,
                      user_won: bool, user_payout: int) -> None:
    """Notifie un participant qu'un pari a ete resolu."""
    if bet.get("resolution_void"):
        outcome = (
            f"Le pari a ete annule (void). Ta mise de {bet['stake']} CAMP "
            f"t'a ete remboursee."
        )
    else:
        winning_label = bet.get("winning_label", "(option inconnue)")
        if user_won:
            outcome = (
                f"Tu as GAGNE ! Option gagnante : {winning_label}. "
                f"Tu touches {user_payout} CAMP."
            )
        else:
            outcome = (
                f"Tu as perdu. Option gagnante : {winning_label}. "
                f"Ta mise de {bet['stake']} CAMP n'a pas ete remboursee."
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
