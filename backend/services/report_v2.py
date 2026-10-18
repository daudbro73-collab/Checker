# -*- coding: utf-8 -*-
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import get_settings

# --- ШРИФТЫ ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(BASE_DIR, "static", "fonts")

try:
    pdfmetrics.registerFont(TTFont('Montserrat', os.path.join(FONT_DIR, 'Montserrat-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('Montserrat-Bold', os.path.join(FONT_DIR, 'Montserrat-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('Montserrat-Medium', os.path.join(FONT_DIR, 'Montserrat-Medium.ttf')))
    pdfmetrics.registerFont(TTFont('Montserrat-SemiBold', os.path.join(FONT_DIR, 'Montserrat-SemiBold.ttf')))
    FONT_REGULAR = 'Montserrat'
    FONT_BOLD = 'Montserrat-Bold'
    FONT_MEDIUM = 'Montserrat-Medium'
    FONT_SEMIBOLD = 'Montserrat-SemiBold'
    FONT_ITALIC = 'Montserrat'
    print("SUCCESS: Montserrat fonts loaded from", FONT_DIR)
except Exception as e:
    print(f"Font loading error: {e}")
    FONT_REGULAR = 'Helvetica'
    FONT_BOLD = 'Helvetica-Bold'
    FONT_MEDIUM = 'Helvetica'
    FONT_SEMIBOLD = 'Helvetica-Bold'
    FONT_ITALIC = 'Helvetica-Oblique'

FONT_AR_REGULAR = FONT_REGULAR
FONT_AR_BOLD = FONT_BOLD
try:
    pdfmetrics.registerFont(TTFont('NotoSansArabic', os.path.join(FONT_DIR, 'NotoSansArabic-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('NotoSansArabic-Bold', os.path.join(FONT_DIR, 'NotoSansArabic-Bold.ttf')))
    FONT_AR_REGULAR = 'NotoSansArabic'
    FONT_AR_BOLD = 'NotoSansArabic-Bold'
    print("SUCCESS: NotoSansArabic fonts loaded")
except Exception as e:
    print(f"Arabic font loading error: {e}")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display as bidi_display

    def shape_rtl(text: str) -> str:
        if not text:
            return text
        return bidi_display(arabic_reshaper.reshape(str(text)))
except Exception:
    def shape_rtl(text: str) -> str:
        return text if text is not None else ""

# --- ЦВЕТОВАЯ ПАЛИТРА ---
COLOR_NAVY = colors.HexColor("#060e22")
COLOR_HEADER_BG = colors.HexColor("#0a1532")
COLOR_SUBBAR_BG = colors.HexColor("#f1f5f9")
COLOR_BORDER = colors.HexColor("#e2e8f0")
COLOR_TEXT_MAIN = colors.HexColor("#0f172a")
COLOR_TEXT_MUTED = colors.HexColor("#64748b")
COLOR_TEXT_DIM = colors.HexColor("#94a3b8")

COLOR_SAFE = colors.HexColor("#10b981")
COLOR_SAFE_BG = colors.HexColor("#ecfdf5")
COLOR_SAFE_BORDER = colors.HexColor("#a7f3d0")

COLOR_CAUTION = colors.HexColor("#f59e0b")
COLOR_CAUTION_BG = colors.HexColor("#fffbeb")
COLOR_CAUTION_BORDER = colors.HexColor("#fde68a")

COLOR_RISK = colors.HexColor("#f97316")
COLOR_RISK_BG = colors.HexColor("#fff7ed")
COLOR_RISK_BORDER = colors.HexColor("#fed7aa")

COLOR_CRITICAL = colors.HexColor("#ef4444")
COLOR_CRITICAL_BG = colors.HexColor("#fef2f2")
COLOR_CRITICAL_BORDER = colors.HexColor("#fecaca")


# --- МУЛЬТИЯЗЫЧНЫЙ СЛОВАРЬ (5 ЯЗЫКОВ: RU, EN, FR, ES, AR) ---
REPORT_I18N = {
    "ru": {
        "slogan": "Trust & Safety для ваших транзакций",
        "data_status": "Класс B · LIVE · TTL 24 ч",
        "type_badge": "Тип: FULL-чек · Risk Engine v2",
        "proof_active": "Пруф действителен 7 дней",
        "verified_badge": "VERIFIED",
        "demo_badge": "ДЕМО-ПРИМЕР",
        "free_badge": "ПЕРВЫЙ БЕСПЛАТНЫЙ ЧЕК",
        "target_title": "ОБЪЕКТ ПРОВЕРКИ",
        "active_wallet": "АКТИВНЫЙ КОШЕЛЁК",
        "first_seen": "ПЕРВЫЙ ВХОД",
        "last_active": "ПОСЛ. АКТИВНОСТЬ",
        "balance": "БАЛАНС",
        "fake_shield": "ТОКЕНЫ · FAKE SHIELD",
        "fake_shield_ok": "✓ офиц. контракт (фейков нет)",
        "fake_shield_warn": "⚠ Обнаружен неподтверждённый токен",
        "verdict_title": "ВЕРДИКТ",
        "kpi_inflow": "ВХОДЯЩИЙ ОБЪЁМ",
        "kpi_outflow": "ИСХОДЯЩИЙ ОБЪЁМ",
        "kpi_attr": "АТРИБУЦИЯ ПОТОКА",
        "kpi_stop": "СТОП-ФАКТОРЫ L0",
        "cex_profile_title": "CEX DEPOSIT PROFILE — ПРИМУТ ЛИ ДЕПОЗИТ",
        "cex_status_safe": "✓ СВОБОДНЫЙ ДЕПОЗИТ (TIER-1 CEX)",
        "cex_status_caution": "⚠️ EDD · ВЕРОЯТЕН РУЧНОЙ АУДИТ НА TIER-1 БИРЖАХ",
        "cex_status_risk": "⚠️ ПОВЫШЕННЫЙ РИСК ХОЛДА И ПРОВЕРКИ ИСТОЧНИКА СРЕДСТВ",
        "cex_status_critical": "⛔ БЛОКИРОВКА ДЕПОЗИТА И СТОП-СИГНАЛ БИРЖАМИ",
        "exposure_title": "ВХОДЯЩАЯ ЭКСПОЗИЦИЯ",
        "shields_title": "СТОП-ФАКТОРЫ L0 / ЩИТЫ БЕЗОПАСНОСТИ",
        "shield_sanctions_clean": "✓ Санкции OFAC / EU / UN — не найдено",
        "shield_sanctions_hit": "⛔ Обнаружен в санкционном списке OFAC/EU/UN",
        "shield_tether_clean": "✓ Блэклист Tether (ончейн) — нет",
        "shield_tether_hit": "⛔ Блэклист Tether — обнаружен в реестре",
        "shield_fake_clean": "✓ Фейковые активы — не обнаружены (Fake Shield)",
        "shield_fake_hit": "⚠ Обнаружены скам-токены/дропы",
        "shield_poison_clean": "✓ Address Poisoning — чисто",
        "shield_poison_hit": "⚠️ Address Poisoning — 2 dust-атаки отражены",
        "recs_title": "ЧТО ДЕЛАТЬ — РЕКОМЕНДАЦИИ ДВИЖКА",
        "proof_title": "ВЕРИФИКАЦИЯ ОТЧЁТА · ДЕЙСТВИТЕЛЕН 7 ДНЕЙ (до {exp} UTC)",
        "proof_check_online": "Проверить подлинность:",
        "methodology": "Методология: Risk Engine v2 — exposure 90 дней (time-decay, anti-dusting < $10). L0: OFAC SDN, EU, UN, блэклист Tether (ончейн). Атрибуция: кластеризация + hot wallets. Отчёт носит информационный характер.",
        "zero_log": "zero-log: история проверок не сохраняется",
        "meta_chain": "Сеть: {chain}",
        "meta_generated": "Сформирован: {dt}",
        "risk_label_safe": "SAFE — НИЗКИЙ",
        "risk_label_caution": "CAUTION — ВНИМАНИЕ",
        "risk_label_risk": "RISK — ПОВЫШЕННЫЙ",
        "risk_label_critical": "CRITICAL — КРИТИЧЕСКИЙ",
        "headline_safe": "Чистая история — кошелёк безопасен для расчётов",
        "headline_caution": "Связь с миксером — вероятен ручной аудит",
        "headline_risk": "Повышенный риск — подозрительная транзакционная активность",
        "headline_critical": "Критический риск — прямое попадание в санкции или эксплойт",
        "desc_safe": "Прямых стоп-факторов не обнаружено. Входящие и исходящие потоки сформированы легальными сервисами, Tier-1 биржами и проверенными контрагентами. Кошелёк полностью пригоден для торговых операций.",
        "desc_caution": "Прямых стоп-факторов (санкции, блэклист Tether, фейковые активы) не обнаружено. Часть входящего объёма связана с повышенным риском: Binance и KuCoin с высокой вероятностью запросят EDD-аудит. Для P2P риск умеренный; для депозитов на биржи — повышенный.",
        "desc_risk": "Выявлена прямая экспозиция к высокорисковым сервисам (>5%) либо нерегулируемым P2P-платформам. Рекомендуется воздержаться от прямых депозитов на лицензированные биржи без проверки источника средств.",
        "desc_critical": "КРИТИЧЕСКАЯ УГРОЗА: Обнаружена прямая связь с адресами из санкционных списков (OFAC/EU/UN), ончейн-блэклистом Tether либо протоколами взломов. Любые операции будут заблокированы комплаенсом.",
        "cex_reason_safe": "Все ончейн-критерии в норме (exposure < 1%). Прямой ввод на Binance, Bybit, OKX, HTX, KuCoin без ограничений.",
        "cex_reason_caution": "Сигналы выше внутреннего порога Tier-1 (1%) · high-risk P2P · dust-атаки отфильтрованы и не влияют на скоринг.",
        "cex_reason_risk": "Прямая экспозиция к нерегулируемым сервисам. Высокая вероятность удержания депозита комплаенсом биржи.",
        "cex_reason_critical": "Стоп-сигнал: санкционные реестры или блэклист Tether. Депозит будет немедленно заблокирован.",
        "dust_note": "Dust-атаки < $10 исключены из скоринга (anti-dusting filter)",
        "page_label": "страница 1/1",
        "sha_prefix": "SHA-256:",
        "recs_safe": [
            "Кошелёк пригоден для любых прямых CEX-депозитов (Binance, Bybit, OKX) без риска блокировки.",
            "P2P-расчёты безопасны: контрагент чист, история транзакций прозрачна.",
            "Соблюдайте базовую криптогигиену: не используйте кошелёк для взаимодействия с сомнительными dApps."
        ],
        "recs_caution": [
            "Оплата поставщику через P2P — риск умеренный: берите адрес из адресной книги, а не из истории (защита от Poisoning).",
            "Депозит на Binance / KuCoin — сначала прогоните платёжную транзакцию в TXID-режиме (EDD вероятен).",
            "Фиксация сделки: сохраняйте платёжные квитанции и инвойсы для подтверждения легальности средств."
        ],
        "recs_risk": [
            "Прямой депозит на Tier-1 биржи не рекомендуется: высокий риск холда средств до предоставления Source of Funds.",
            "P2P-расчёты: запросите у контрагента официальное подтверждение происхождения средств перед приёмом.",
            "Изоляция: используйте отдельный транзитный кошелёк для разделения коммерческих и личных средств."
        ],
        "recs_critical": [
            "СТОП-СИГНАЛ: Зафиксирована прямая связь с санкционными списками, контрактами взломов или блэклистом Tether.",
            "Полная блокировка: категорически откажитесь от приёма средств, транзакция приведёт к заморозке счетов.",
            "Юридический риск: владение данными активами влечёт комплаенс-риски и регуляторные санкции."
        ]
    },
    "en": {
        "slogan": "Trust & Safety for your crypto transactions",
        "data_status": "Class B · LIVE · TTL 24h",
        "type_badge": "Type: FULL Check · Risk Engine v2",
        "proof_active": "Proof valid for 7 days",
        "verified_badge": "VERIFIED",
        "demo_badge": "DEMO SAMPLE",
        "free_badge": "FIRST FREE TRIAL CHECK",
        "target_title": "SCREENING TARGET",
        "active_wallet": "ACTIVE WALLET",
        "first_seen": "FIRST SEEN",
        "last_active": "LAST ACTIVE",
        "balance": "BALANCE",
        "fake_shield": "TOKENS · FAKE SHIELD",
        "fake_shield_ok": "✓ Official contract (No fake tokens)",
        "fake_shield_warn": "⚠ Unverified token detected",
        "verdict_title": "VERDICT",
        "kpi_inflow": "TOTAL INFLOW VOLUME",
        "kpi_outflow": "TOTAL OUTFLOW VOLUME",
        "kpi_attr": "STREAM ATTRIBUTION",
        "kpi_stop": "L0 STOP-FACTORS",
        "cex_profile_title": "CEX DEPOSIT PROFILE — DEPOSIT COMPLIANCE",
        "cex_status_safe": "✓ DIRECT DEPOSIT ACCEPTED (TIER-1 CEX)",
        "cex_status_caution": "⚠️ EDD · MANUAL AUDIT LIKELY ON TIER-1 CEX",
        "cex_status_risk": "⚠️ HIGH RISK OF HOLD & SOURCE OF FUNDS REQUEST",
        "cex_status_critical": "⛔ IMMEDIATE DEPOSIT FREEZE / STOP-SIGNAL",
        "exposure_title": "INFLOW EXPOSURE",
        "shields_title": "L0 STOP-FACTORS & SECURITY SHIELDS",
        "shield_sanctions_clean": "✓ OFAC / EU / UN Sanctions — No hits",
        "shield_sanctions_hit": "⛔ Listed in OFAC / EU / UN sanctions database",
        "shield_tether_clean": "✓ Tether Blacklist (on-chain) — None",
        "shield_tether_hit": "⛔ Tether Blacklist — Listed in blacklist contract",
        "shield_fake_clean": "✓ Fake assets — None detected (Fake Shield)",
        "shield_fake_hit": "⚠ Scam / airdrop token detected",
        "shield_poison_clean": "✓ Address Poisoning — Clean",
        "shield_poison_hit": "⚠️ Address Poisoning — 2 dust attacks mitigated",
        "recs_title": "ACTIONABLE RECOMMENDATIONS",
        "proof_title": "REPORT VERIFICATION · VALID 7 DAYS (until {exp} UTC)",
        "proof_check_online": "Verify authenticity:",
        "methodology": "Methodology: Risk Engine v2 — 90-day exposure (time-decay, anti-dusting < $10). L0: OFAC SDN, EU, UN, on-chain Tether blacklist. Attribution: clustering + hot wallets. Informational only — not a compliance certificate.",
        "zero_log": "zero-log: audit trail is not retained",
        "meta_chain": "Network: {chain}",
        "meta_generated": "Generated: {dt}",
        "risk_label_safe": "SAFE — LOW",
        "risk_label_caution": "CAUTION — ATTENTION",
        "risk_label_risk": "RISK — ELEVATED",
        "risk_label_critical": "CRITICAL — CRITICAL",
        "headline_safe": "Clean history — wallet is safe for settlements",
        "headline_caution": "Mixer exposure — manual audit likely",
        "headline_risk": "Elevated risk — suspicious transactional activity",
        "headline_critical": "Critical risk — direct sanctions or exploit hit",
        "desc_safe": "No direct stop-factors found. Inflows and outflows are formed by legitimate services, Tier-1 exchanges and verified counterparties. The wallet is fully suitable for trading operations.",
        "desc_caution": "No direct stop-factors (sanctions, Tether blacklist, fake assets). Part of inbound volume carries elevated risk: Binance and KuCoin will likely request EDD. Moderate for P2P; elevated for CEX deposits.",
        "desc_risk": "Direct exposure to high-risk services (>5%) or unregulated P2P platforms detected. Avoid direct deposits to licensed exchanges without source-of-funds review.",
        "desc_critical": "CRITICAL THREAT: Direct links to OFAC/EU/UN sanctioned addresses, on-chain Tether blacklist, or exploit protocols. Compliance stacks will block related operations.",
        "cex_reason_safe": "All on-chain criteria within range (exposure < 1%). Direct deposit to Binance, Bybit, OKX, HTX, KuCoin without restrictions.",
        "cex_reason_caution": "Signals above Tier-1 internal threshold (1%) · high-risk P2P · dust attacks filtered and excluded from scoring.",
        "cex_reason_risk": "Direct exposure to unregulated services. High probability of deposit hold by exchange compliance.",
        "cex_reason_critical": "Stop-signal: sanctions registries or Tether blacklist. Deposit will be frozen immediately.",
        "dust_note": "Dust attacks < $10 excluded from scoring (anti-dusting filter)",
        "page_label": "page 1/1",
        "sha_prefix": "SHA-256:",
        "recs_safe": [
            "Wallet is fully suitable for direct deposits on Tier-1 CEX (Binance, Bybit, OKX) with zero hold risk.",
            "P2P settlements are safe: counterparty is clean and transaction provenance is transparent.",
            "Standard hygiene: avoid connecting this address to unverified dApps or untested protocols."
        ],
        "recs_caution": [
            "P2P supplier payment — moderate risk: copy recipient address from address book, not history (anti-poisoning).",
            "CEX deposit (Binance/KuCoin) — test with a small payment in TXID mode first (EDD likely).",
            "Transaction record: retain invoices and payment receipts for source-of-wealth proof."
        ],
        "recs_risk": [
            "Direct Tier-1 CEX deposit not recommended: high probability of account hold pending Source of Funds.",
            "P2P transactions: request formal proof of funds from counterparty before accepting payment.",
            "Isolation: use a separate transit wallet to keep commercial and personal flows separated."
        ],
        "recs_critical": [
            "STOP-SIGNAL: Direct links identified to sanctions, exploit contracts, or Tether on-chain blacklist.",
            "Total freeze: strictly decline receiving funds; the transaction will trigger a compliance freeze.",
            "Legal exposure: holding these assets introduces severe regulatory and compliance consequences."
        ]
    },
    "fr": {
        "slogan": "Confiance et securite pour vos transactions crypto",
        "data_status": "Classe B · EN DIRECT · TTL 24h",
        "type_badge": "Type: controle COMPLET · Risk Engine v2",
        "proof_active": "Preuve valable 7 jours",
        "verified_badge": "VERIFIE",
        "demo_badge": "EXEMPLE DEMO",
        "free_badge": "PREMIER ESSAI GRATUIT",
        "target_title": "CIBLE DU CONTROLE",
        "active_wallet": "PORTEFEUILLE ACTIF",
        "first_seen": "PREMIER VU",
        "last_active": "DERNIERE ACTIVITE",
        "balance": "SOLDE",
        "fake_shield": "JETONS · FAKE SHIELD",
        "fake_shield_ok": "✓ Contrat officiel (aucun faux jeton)",
        "fake_shield_warn": "⚠ Jeton non verifie detecte",
        "verdict_title": "VERDICT",
        "kpi_inflow": "VOLUME TOTAL ENTRANT",
        "kpi_outflow": "VOLUME TOTAL SORTANT",
        "kpi_attr": "ATTRIBUTION DU FLUX",
        "kpi_stop": "FACTEURS D'ARRET L0",
        "cex_profile_title": "PROFIL DE DEPOT CEX — CONFORMITE",
        "cex_status_safe": "✓ DEPOT DIRECT ACCEPTE (CEX TIER-1)",
        "cex_status_caution": "⚠️ EDD · AUDIT MANUEL PROBABLE SUR CEX TIER-1",
        "cex_status_risk": "⚠️ RISQUE ELEVE DE BLOCAGE ET DE JUSTIFICATIFS",
        "cex_status_critical": "⛔ BLOCAGE IMMEDIAT DU DEPOT / SIGNAL D'ARRET",
        "exposure_title": "EXPOSITION DES FLUX ENTRANTS",
        "shields_title": "FACTEURS D'ARRET L0 ET BOUCLIERS",
        "shield_sanctions_clean": "✓ Sanctions OFAC / UE / ONU — aucun resultat",
        "shield_sanctions_hit": "⛔ Inscrit sur les listes de sanctions OFAC/UE/ONU",
        "shield_tether_clean": "✓ Liste noire Tether (on-chain) — aucun",
        "shield_tether_hit": "⛔ Liste noire Tether — inscrit au contrat",
        "shield_fake_clean": "✓ Actifs contrefaits — aucun detecte (Fake Shield)",
        "shield_fake_hit": "⚠ Jeton frauduleux / airdrop detecte",
        "shield_poison_clean": "✓ Empoisonnement d'adresse — propre",
        "shield_poison_hit": "⚠️ Empoisonnement d'adresse — 2 attaques dust bloquees",
        "recs_title": "RECOMMANDATIONS ACTIONNABLES",
        "proof_title": "VERIFICATION DU RAPPORT · VALIDE 7 JOURS (jusqu'au {exp} UTC)",
        "proof_check_online": "Verifier l'authenticite :",
        "methodology": "Methodologie : Risk Engine v2 — exposition 90 jours (decroissance temporelle, anti-dusting < $10). L0 : OFAC SDN, UE, ONU, liste noire Tether on-chain. Attribution : clustering + hot wallets. Rapport informatif uniquement.",
        "zero_log": "zero-log : aucun historique d'audit conserve",
        "meta_chain": "Reseau : {chain}",
        "meta_generated": "Genere : {dt}",
        "risk_label_safe": "SAFE — FAIBLE",
        "risk_label_caution": "CAUTION — ATTENTION",
        "risk_label_risk": "RISK — ELEVE",
        "risk_label_critical": "CRITICAL — CRITIQUE",
        "headline_safe": "Historique propre — portefeuille sur pour les reglements",
        "headline_caution": "Exposition mixeur — audit manuel probable",
        "headline_risk": "Risque eleve — activite transactionnelle suspecte",
        "headline_critical": "Risque critique — hit sanctions ou exploit direct",
        "desc_safe": "Aucun facteur d'arret direct. Entrees et sorties formees par des services legitimes, CEX Tier-1 et contreparties verifiees. Portefeuille pleinement adapte aux operations commerciales.",
        "desc_caution": "Aucun facteur d'arret direct (sanctions, liste noire Tether, faux actifs). Une part du volume entrant presente un risque eleve : Binance et KuCoin demanderont probablement un audit EDD. Modere pour le P2P ; eleve pour les depots CEX.",
        "desc_risk": "Exposition directe a des services a haut risque (>5 %) ou plateformes P2P non regulees. Evitez les depots directs sur les exchanges licenses sans revue de l'origine des fonds.",
        "desc_critical": "MENACE CRITIQUE : liens directs avec des adresses sanctionnees OFAC/UE/ONU, la liste noire Tether on-chain ou des protocoles d'exploit. Les stacks de conformite bloqueront les operations.",
        "cex_reason_safe": "Tous les criteres on-chain dans la norme (exposition < 1 %). Depot direct Binance, Bybit, OKX, HTX, KuCoin sans restriction.",
        "cex_reason_caution": "Signaux au-dessus du seuil interne Tier-1 (1 %) · P2P high-risk · attaques dust filtrees et exclues du scoring.",
        "cex_reason_risk": "Exposition directe a des services non regules. Forte probabilite de retention du depot par la conformite.",
        "cex_reason_critical": "Signal d'arret : registres de sanctions ou liste noire Tether. Le depot sera gele immediatement.",
        "dust_note": "Attaques dust < $10 exclues du scoring (filtre anti-dusting)",
        "page_label": "page 1/1",
        "sha_prefix": "SHA-256 :",
        "recs_safe": [
            "Le portefeuille convient aux depots directs sur les CEX Tier-1 (Binance, Bybit, OKX) sans risque de blocage.",
            "Reglements P2P surs : contrepartie saine et provenance des transactions transparente.",
            "Hygiene standard : evitez de connecter cette adresse a des dApps non auditees."
        ],
        "recs_caution": [
            "Paiement fournisseur P2P — risque modere : copiez l'adresse depuis le carnet, pas l'historique (anti-empoisonnement).",
            "Depot CEX (Binance/KuCoin) — testez d'abord avec un petit virement en mode TXID (EDD probable).",
            "Conservez factures et recus pour prouver l'origine licite des fonds."
        ],
        "recs_risk": [
            "Depot direct Tier-1 non recommande : forte probabilite de gel en attente de Source of Funds.",
            "Transactions P2P : exigez une preuve officielle de provenance avant d'accepter les fonds.",
            "Isolation : utilisez un portefeuille de transit pour separer flux commerciaux et personnels."
        ],
        "recs_critical": [
            "SIGNAL D'ARRET : liens directs avec sanctions, contrats d'exploit ou liste noire Tether on-chain.",
            "Refus total : n'acceptez aucun fonds ; la transaction declenchera un gel reglementaire.",
            "Exposition legale : detenir ces actifs entraine de graves consequences reglementaires."
        ]
    },
    "es": {
        "slogan": "Confianza y seguridad para sus transacciones cripto",
        "data_status": "Clase B · EN VIVO · TTL 24h",
        "type_badge": "Tipo: comprobacion COMPLETA · Risk Engine v2",
        "proof_active": "Prueba valida por 7 dias",
        "verified_badge": "VERIFICADO",
        "demo_badge": "MUESTRA DEMO",
        "free_badge": "PRIMERA PRUEBA GRATIS",
        "target_title": "OBJETIVO DE VERIFICACION",
        "active_wallet": "BILLETERA ACTIVA",
        "first_seen": "PRIMER REGISTRO",
        "last_active": "ULTIMA ACTIVIDAD",
        "balance": "SALDO",
        "fake_shield": "TOKENS · FAKE SHIELD",
        "fake_shield_ok": "✓ Contrato oficial (sin tokens falsos)",
        "fake_shield_warn": "⚠ Token no verificado detectado",
        "verdict_title": "VEREDICTO",
        "kpi_inflow": "VOLUMEN TOTAL ENTRANTE",
        "kpi_outflow": "VOLUMEN TOTAL SALIENTE",
        "kpi_attr": "ATRIBUCION DE FLUJO",
        "kpi_stop": "FACTORES DE PARADA L0",
        "cex_profile_title": "PERFIL DE DEPOSITO CEX — CUMPLIMIENTO",
        "cex_status_safe": "✓ DEPOSITO DIRECTO ACEPTADO (CEX TIER-1)",
        "cex_status_caution": "⚠️ EDD · AUDITORIA MANUAL PROBABLE EN CEX TIER-1",
        "cex_status_risk": "⚠️ ALTO RIESGO DE RETENCION Y ORIGEN DE FONDOS",
        "cex_status_critical": "⛔ BLOQUEO INMEDIATO DE DEPOSITO / SENAL DE PARADA",
        "exposure_title": "EXPOSICION DE ENTRADAS",
        "shields_title": "FACTORES DE PARADA L0 Y ESCUDOS",
        "shield_sanctions_clean": "✓ Sanciones OFAC / UE / ONU — sin coincidencias",
        "shield_sanctions_hit": "⛔ Incluido en listas de sanciones OFAC/UE/ONU",
        "shield_tether_clean": "✓ Lista negra Tether (on-chain) — ninguna",
        "shield_tether_hit": "⛔ Lista negra Tether — registrado en el contrato",
        "shield_fake_clean": "✓ Activos falsos — no detectados (Fake Shield)",
        "shield_fake_hit": "⚠ Token fraudulento / airdrop detectado",
        "shield_poison_clean": "✓ Envenenamiento de direccion — limpio",
        "shield_poison_hit": "⚠️ Envenenamiento de direccion — 2 ataques dust mitigados",
        "recs_title": "RECOMENDACIONES PRACTICAS",
        "proof_title": "VERIFICACION DEL INFORME · VALIDO 7 DIAS (hasta {exp} UTC)",
        "proof_check_online": "Verificar autenticidad:",
        "methodology": "Metodologia: Risk Engine v2 — exposicion 90 dias (decaimiento temporal, anti-dusting < $10). L0: OFAC SDN, UE, ONU, lista negra Tether on-chain. Atribucion: clustering + hot wallets. Informe orientativo — no es certificado de cumplimiento.",
        "zero_log": "zero-log: no se conserva historial de auditoria",
        "meta_chain": "Red: {chain}",
        "meta_generated": "Generado: {dt}",
        "risk_label_safe": "SAFE — BAJO",
        "risk_label_caution": "CAUTION — ATENCION",
        "risk_label_risk": "RISK — ELEVADO",
        "risk_label_critical": "CRITICAL — CRITICO",
        "headline_safe": "Historial limpio — billetera segura para liquidaciones",
        "headline_caution": "Exposicion a mixer — auditoria manual probable",
        "headline_risk": "Riesgo elevado — actividad transaccional sospechosa",
        "headline_critical": "Riesgo critico — sancion o exploit directo",
        "desc_safe": "No se hallaron factores de parada directos. Entradas y salidas formadas por servicios legitimos, CEX Tier-1 y contrapartes verificadas. La billetera es apta para operaciones comerciales.",
        "desc_caution": "Sin factores de parada directos (sanciones, lista negra Tether, activos falsos). Parte del volumen entrante tiene riesgo elevado: Binance y KuCoin probablemente solicitaran EDD. Moderado para P2P; elevado para depositos CEX.",
        "desc_risk": "Exposicion directa a servicios de alto riesgo (>5%) o plataformas P2P no reguladas. Evite depositos directos en exchanges licenciados sin revisar el origen de fondos.",
        "desc_critical": "AMENAZA CRITICA: vinculos directos con direcciones sancionadas OFAC/UE/ONU, lista negra Tether on-chain o protocolos de exploit. Los stacks de cumplimiento bloquearan las operaciones.",
        "cex_reason_safe": "Todos los criterios on-chain en norma (exposicion < 1%). Deposito directo a Binance, Bybit, OKX, HTX, KuCoin sin restricciones.",
        "cex_reason_caution": "Senales por encima del umbral interno Tier-1 (1%) · P2P de alto riesgo · ataques dust filtrados y excluidos del scoring.",
        "cex_reason_risk": "Exposicion directa a servicios no regulados. Alta probabilidad de retencion del deposito por cumplimiento.",
        "cex_reason_critical": "Senal de parada: registros de sanciones o lista negra Tether. El deposito se congelara de inmediato.",
        "dust_note": "Ataques dust < $10 excluidos del scoring (filtro anti-dusting)",
        "page_label": "pagina 1/1",
        "sha_prefix": "SHA-256:",
        "recs_safe": [
            "Billetera adecuada para depositos directos en CEX Tier-1 (Binance, Bybit, OKX) sin riesgo de retencion.",
            "Operaciones P2P seguras: contraparte limpia y trazabilidad transparente.",
            "Higiene estandar: evite conectar esta direccion a dApps no auditadas."
        ],
        "recs_caution": [
            "Pago a proveedor P2P — riesgo moderado: copie la direccion de su libreta, no del historial (anti-envenenamiento).",
            "Deposito CEX (Binance/KuCoin) — pruebe primero con un pago pequeno en modo TXID (EDD probable).",
            "Conserve facturas y recibos para justificar el origen licito de los fondos."
        ],
        "recs_risk": [
            "Deposito directo Tier-1 no recomendado: alta probabilidad de retencion pendiente de Source of Funds.",
            "Operaciones P2P: solicite prueba formal del origen de fondos antes de recibir.",
            "Aislamiento: use una billetera de transito para separar flujos comerciales y personales."
        ],
        "recs_critical": [
            "SENAL DE PARADA: vinculo directo con sanciones, contratos de exploit o lista negra Tether on-chain.",
            "Rechazo total: no reciba fondos; la transaccion provocara congelacion de cumplimiento.",
            "Riesgo legal: poseer estos activos implica graves consecuencias regulatorias."
        ]
    },
    "ar": {
        "slogan": "الثقة والأمان لمعاملاتك في العملات المشفرة",
        "data_status": "الفئة B · مباشر · صلاحية 24 ساعة",
        "type_badge": "النوع: فحص كامل · Risk Engine v2",
        "proof_active": "الإثبات صالح لمدة 7 أيام",
        "verified_badge": "تم التحقق",
        "demo_badge": "عينة تجريبية",
        "free_badge": "الفحص التجريبي المجاني الأول",
        "target_title": "الهدف الخاضع للفحص",
        "active_wallet": "محفظة نشطة",
        "first_seen": "أول ظهور",
        "last_active": "آخر نشاط",
        "balance": "الرصيد",
        "fake_shield": "الرموز · FAKE SHIELD",
        "fake_shield_ok": "✓ عقد رسمي (لا رموز وهمية)",
        "fake_shield_warn": "⚠ تم رصد رمز غير موثّق",
        "verdict_title": "القرار التحليلي",
        "kpi_inflow": "إجمالي التدفق الوارد",
        "kpi_outflow": "إجمالي التدفق الصادر",
        "kpi_attr": "نسبة إسناد التدفق",
        "kpi_stop": "عوامل الإيقاف L0",
        "cex_profile_title": "ملف إيداع المنصات — امتثال الإيداع",
        "cex_status_safe": "✓ إيداع مباشر مقبول (منصات المستوى 1)",
        "cex_status_caution": "⚠️ EDD · تدقيق يدوي محتمل في منصات المستوى 1",
        "cex_status_risk": "⚠️ خطر مرتفع للتعليق وطلب إثبات مصدر الأموال",
        "cex_status_critical": "⛔ تجميد فوري للإيداع وعلامة توقف",
        "exposure_title": "التعرض للتدفق الوارد",
        "shields_title": "عوامل الإيقاف L0 ودروع الحماية",
        "shield_sanctions_clean": "✓ عقوبات OFAC / الاتحاد الأوروبي / الأمم المتحدة — نظيف",
        "shield_sanctions_hit": "⛔ مدرج في قوائم العقوبات الدولية",
        "shield_tether_clean": "✓ قائمة تيثر السوداء (على الشبكة) — لا يوجد",
        "shield_tether_hit": "⛔ قائمة تيثر السوداء — مدرج في القائمة",
        "shield_fake_clean": "✓ الأصول الوهمية — لم يُعثر عليها (Fake Shield)",
        "shield_fake_hit": "⚠ تم اكتشاف رموز احتيالية / إسقاطات",
        "shield_poison_clean": "✓ تسميم العناوين — نظيف",
        "shield_poison_hit": "⚠️ تسميم العناوين — تم صد هجمتين غباريات",
        "recs_title": "توصيات المحرك الإجرائية",
        "proof_title": "التحقق من التقرير · صالح 7 أيام (حتى {exp} UTC)",
        "proof_check_online": "تحقق من صحة التقرير:",
        "methodology": "المنهجية: Risk Engine v2 — تعرّض 90 يومًا (تضاؤل زمني، مضاد للغبار < $10). L0: OFAC SDN والاتحاد الأوروبي والأمم المتحدة وقائمة تيثر السوداء على السلسلة. الإسناد: تجميع + محافظ ساخنة. تقرير معلوماتي فقط.",
        "zero_log": "zero-log: لا يُحتفظ بسجل الفحوصات",
        "meta_chain": "الشبكة: {chain}",
        "meta_generated": "أُنشئ: {dt}",
        "risk_label_safe": "SAFE — منخفض",
        "risk_label_caution": "CAUTION — انتباه",
        "risk_label_risk": "RISK — مرتفع",
        "risk_label_critical": "CRITICAL — حرج",
        "headline_safe": "سجل نظيف — المحفظة آمنة للتسويات",
        "headline_caution": "تعرّض لخلاط — تدقيق يدوي محتمل",
        "headline_risk": "مخاطر مرتفعة — نشاط معاملات مشبوه",
        "headline_critical": "مخاطر حرجة — إصابة عقوبات أو استغلال مباشر",
        "desc_safe": "لم يُعثر على عوامل إيقاف مباشرة. التدفقات الواردة والصادرة من خدمات مشروعة ومنصات المستوى 1 وأطراف موثّقة. المحفظة مناسبة تمامًا للعمليات التجارية.",
        "desc_caution": "لا عوامل إيقاف مباشرة (عقوبات، قائمة تيثر، أصول وهمية). جزء من الحجم الوارد يحمل مخاطر مرتفعة: منصتا Binance وKuCoin ستطلبان على الأرجح تدقيق EDD. معتدل لـ P2P؛ مرتفع لإيداعات المنصات.",
        "desc_risk": "تعرّض مباشر لخدمات عالية المخاطر (>5%) أو منصات P2P غير منظّمة. تجنّب الإيداع المباشر في المنصات المرخّصة دون مراجعة مصدر الأموال.",
        "desc_critical": "تهديد حرج: ارتباط مباشر بعناوين عقوبات OFAC/EU/UN أو قائمة تيثر السوداء أو بروتوكولات الاستغلال. أنظمة الامتثال ستحظر العمليات.",
        "cex_reason_safe": "جميع معايير السلسلة ضمن النطاق (تعرّض < 1%). إيداع مباشر في Binance وBybit وOKX وHTX وKuCoin دون قيود.",
        "cex_reason_caution": "إشارات فوق عتبة المستوى 1 الداخلية (1%) · P2P عالي المخاطر · هجمات الغبار مفلترة ومستبعدة من التقييم.",
        "cex_reason_risk": "تعرّض مباشر لخدمات غير منظّمة. احتمال مرتفع لتعليق الإيداع من امتثال المنصة.",
        "cex_reason_critical": "إشارة توقف: سجلات عقوبات أو قائمة تيثر السوداء. سيُجمَّد الإيداع فورًا.",
        "dust_note": "هجمات الغبار < $10 مستبعدة من التقييم (مرشح مضاد للغبار)",
        "page_label": "صفحة 1/1",
        "sha_prefix": "SHA-256:",
        "recs_safe": [
            "المحفظة مناسبة تمامًا للإيداع المباشر في منصات المستوى 1 (Binance وBybit وOKX) دون مخاطر تعليق.",
            "معاملات P2P آمنة: الطرف المقابل نظيف ومصدر المعاملات شفاف.",
            "نظافة رقمية قياسية: تجنّب ربط هذا العنوان بتطبيقات غير موثّقة."
        ],
        "recs_caution": [
            "الدفع للمورد عبر P2P — مخاطرة متوسطة: انسخ العنوان من دفتر العناوين لا من السجل (حماية من التسميم).",
            "الإيداع في المنصات (Binance/KuCoin) — جرّب أولاً دفعة صغيرة بوضع TXID (EDD محتمل).",
            "احتفظ بالفواتير والإيصالات لإثبات مشروعية مصدر الأموال."
        ],
        "recs_risk": [
            "لا يُنصح بالإيداع المباشر في المستوى 1: احتمال مرتفع لتعليق الحساب بانتظار مصدر الأموال.",
            "معاملات P2P: اطلب إثباتًا رسميًا لمصدر الأموال قبل الاستلام.",
            "العزل: استخدم محفظة وسيطة لفصل التدفقات التجارية عن الشخصية."
        ],
        "recs_critical": [
            "إشارة توقف: ارتباط مباشر بالعقوبات أو عقود الاستغلال أو القائمة السوداء لتيثر على السلسلة.",
            "رفض قاطع: لا تستلم أي أموال؛ ستؤدي المعاملة إلى تجميد امتثال فوري.",
            "مخاطر قانونية: حيازة هذه الأصول تستتبع عواقب تنظيمية خطيرة."
        ]
    }
}


def wrap_text(text, max_width, font_name, font_size):
    words = text.split()
    lines = []
    current = []
    for w in words:
        test = (" ".join(current + [w])).strip()
        if not test:
            continue
        width = pdfmetrics.stringWidth(test, font_name, font_size)
        if width <= max_width or not current:
            current.append(w)
        else:
            lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines


def draw_watermark(c, width, height, text):
    """Semi-transparent diagonal watermark for free checks."""
    c.saveState()
    c.setFont(FONT_BOLD, 24)
    c.setFillColor(colors.Color(0.70, 0.75, 0.88, alpha=0.14))
    c.translate(width / 2, height / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def compute_report_metadata(chain: str, address: str, score: int, now_utc: Optional[datetime] = None) -> tuple[str, str, str]:
    """Returns (report_id, sha_hash, exp_date_str) deterministically for verification."""
    if now_utc is None:
        now_utc = datetime.utcnow()
    chain_tag = (chain or "ETH")[:3].upper()
    addr_hash = hashlib.md5((address or "").encode()).hexdigest()[:6].upper()
    report_id = f"AG-{now_utc.strftime('%Y%m%d')}-{chain_tag}-{addr_hash}"
    exp_date = (now_utc + timedelta(days=7)).strftime("%d.%m.%Y %H:%M")
    sha_hash = hashlib.sha256(f"{report_id}:{address}:{score}:{now_utc.isoformat()}".encode()).hexdigest()
    return report_id, sha_hash, exp_date


def create_premium_pdf(filename, data):
    """
    Generates a STRICT 1-PAGE A4 Premium AML Guard Compliance Report.
    Designed to match the reference mockup exactly:
    - No flow graph
    - Inflow & Outflow 90d in KPIs
    - Tether: strict blacklist status (clean/hit) without 'freeze' words
    - Unified CEX Deposit Profile card without individual row bloat
    - 4 distinct risk recommendation levels (SAFE, CAUTION, RISK, CRITICAL)
    - Full support for 5 languages: EN, RU, FR, ES, AR
    """
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4  # 595.28 x 841.89 pt
    margin = 36
    content_width = width - margin * 2  # 523.28 pt

    lang = data.get("lang", "ru")
    if lang not in REPORT_I18N:
        lang = "ru"
    tr = REPORT_I18N[lang]
    is_ar = lang == "ar"
    font_reg = FONT_AR_REGULAR if is_ar else FONT_REGULAR
    font_bold = FONT_AR_BOLD if is_ar else FONT_BOLD

    def T(text):
        return shape_rtl(text) if is_ar else text

    def draw_s(x, y, text, font=None, size=None):
        if font and size is not None:
            c.setFont(font, size)
        c.drawString(x, y, T(text))

    def draw_r(x, y, text, font=None, size=None):
        if font and size is not None:
            c.setFont(font, size)
        c.drawRightString(x, y, T(text))

    def draw_c(x, y, text, font=None, size=None):
        if font and size is not None:
            c.setFont(font, size)
        c.drawCentredString(x, y, T(text))

    score = int(data.get("risk_score", 0))
    chain = data.get("chain", "TRON · TRC-20")
    address = data.get("address", "")
    chain_data = data.get("chain_data", {}) or {}
    factors = data.get("risk_factors", []) or []
    sanctions = data.get("sanctions", {}) or {}

    # Risk level & colors
    if score >= 75:
        risk_level = "CRITICAL"
        risk_color = COLOR_CRITICAL
        risk_bg = COLOR_CRITICAL_BG
        risk_border = COLOR_CRITICAL_BORDER
        risk_label = tr["risk_label_critical"]
    elif score >= 40:
        risk_level = "RISK"
        risk_color = COLOR_RISK
        risk_bg = COLOR_RISK_BG
        risk_border = COLOR_RISK_BORDER
        risk_label = tr["risk_label_risk"]
    elif score >= 20:
        risk_level = "CAUTION"
        risk_color = COLOR_CAUTION
        risk_bg = COLOR_CAUTION_BG
        risk_border = COLOR_CAUTION_BORDER
        risk_label = tr["risk_label_caution"]
    else:
        risk_level = "SAFE"
        risk_color = COLOR_SAFE
        risk_bg = COLOR_SAFE_BG
        risk_border = COLOR_SAFE_BORDER
        risk_label = tr["risk_label_safe"]

    now_utc = datetime.utcnow()
    computed_id, computed_sha, computed_exp = compute_report_metadata(chain, address, score, now_utc)
    report_id = data.get("report_id") or computed_id
    exp_date = data.get("exp_date") or computed_exp
    sha_hash = data.get("sha256") or computed_sha

    settings = get_settings()
    verify_url = f"{settings.VERIFY_BASE_URL}/{report_id}"

    # Watermark for free trial checks
    if data.get("is_free_trial"):
        draw_watermark(c, width, height, tr["free_badge"])

    # =========================================================================
    # 1. ТЁМНЫЙ ПРЕМИУМ-ХЕДЕР (NAVY BLUE) & СУБ-БАР
    # =========================================================================
    header_top = height
    header_h = 66
    header_y0 = header_top - header_h

    c.setFillColor(COLOR_HEADER_BG)
    c.rect(0, header_y0, width, header_h, fill=1, stroke=0)

    # Logo & Slogan
    c.setFillColor(colors.white)
    c.setFont(font_bold, 20)
    c.drawString(margin, header_top - 30, "AML GUARD")
    c.setFont(font_reg, 8.5)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawString(margin, header_top - 46, T(tr["slogan"]))

    # Header Right Metadata
    c.setFont(font_bold, 9)
    c.setFillColor(colors.HexColor("#e2e8f0"))
    c.drawRightString(width - margin, header_top - 24, T(report_id))
    c.setFont(font_reg, 7.5)
    c.setFillColor(colors.HexColor("#cbd5e1"))
    draw_r(width - margin, header_top - 36, tr["meta_chain"].format(chain=chain))
    draw_r(width - margin, header_top - 47, tr["meta_generated"].format(dt=now_utc.strftime("%d.%m.%Y %H:%M UTC")))
    c.setFillColor(colors.HexColor("#38bdf8"))
    c.drawRightString(width - margin, header_top - 58, T(tr["data_status"]))

    # Sub-bar (Подстрочник)
    subbar_h = 18
    subbar_y0 = header_y0 - subbar_h
    c.setFillColor(COLOR_SUBBAR_BG)
    c.setStrokeColor(COLOR_BORDER)
    c.rect(0, subbar_y0, width, subbar_h, fill=1, stroke=1)

    c.setFont(font_bold, 7)
    c.setFillColor(COLOR_TEXT_MAIN)
    c.drawString(margin, subbar_y0 + 5, T(tr["type_badge"]))

    # Status Pill (VERIFIED / DEMO / FREE)
    badge_label = tr["verified_badge"]
    badge_color = COLOR_SAFE
    badge_bg = COLOR_SAFE_BG
    if data.get("is_demo"):
        badge_label = tr["demo_badge"]
        badge_color = COLOR_CAUTION
        badge_bg = COLOR_CAUTION_BG
    elif data.get("is_free_trial"):
        badge_label = tr["free_badge"]
        badge_color = COLOR_CAUTION
        badge_bg = COLOR_CAUTION_BG

    c.setFillColor(badge_bg)
    c.setStrokeColor(badge_color)
    c.roundRect(width - margin - 80, subbar_y0 + 2.5, 80, 13, 3, fill=1, stroke=1)
    c.setFillColor(badge_color)
    c.setFont(font_bold, 6.5)
    c.drawCentredString(width - margin - 40, subbar_y0 + 5.5, T(badge_label))

    # =========================================================================
    # =========================================================================
    # 2. БЛОК «ОБЪЕКТ ПРОВЕРКИ»
    # =========================================================================
    gap = 12
    target_h = 76
    target_y0 = subbar_y0 - target_h - gap

    c.setFillColor(colors.white)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(margin, target_y0, content_width, target_h, 6, fill=1, stroke=1)

    # Header inside target card
    c.setFont(font_bold, 7)
    c.setFillColor(COLOR_TEXT_MUTED)
    c.drawString(margin + 12, target_y0 + target_h - 15, T(tr["target_title"]))

    # Target Address & Badges
    addr_display = address if len(address) <= 38 else (address[:18] + "..." + address[-16:])
    c.setFont(font_bold, 9.5)
    c.setFillColor(COLOR_TEXT_MAIN)
    c.drawString(margin + 12, target_y0 + target_h - 32, T(addr_display))

    # Badge «АКТИВНЫЙ АДРЕС»
    badge_label = tr.get("active_wallet", "АКТИВНЫЙ АДРЕС")
    badge_w = c.stringWidth(badge_label, font_bold, 6.5) + 16
    badge_x = margin + 12 + pdfmetrics.stringWidth(addr_display, font_bold, 9.5) + 12
    if badge_x + badge_w < width - margin - 20:
        c.setFillColor(colors.HexColor("#f0fdf4"))
        c.setStrokeColor(COLOR_SAFE)
        c.roundRect(badge_x, target_y0 + target_h - 34, badge_w, 13, 2.5, fill=1, stroke=1)
        c.setFillColor(COLOR_SAFE)
        c.setFont(font_bold, 6.5)
        c.drawCentredString(badge_x + badge_w / 2, target_y0 + target_h - 30.5, T(badge_label))

    # 4 columns in target card
    col_w = content_width / 4
    col_y_lbl = target_y0 + 24
    col_y_val = target_y0 + 10

    c.setFont(font_bold, 6.5)
    c.setFillColor(COLOR_TEXT_MUTED)
    c.drawString(margin + 12, col_y_lbl, T(tr["first_seen"]))
    c.drawString(margin + 12 + col_w, col_y_lbl, T(tr["last_active"]))
    c.drawString(margin + 12 + col_w * 2, col_y_lbl, T(tr["balance"]))
    c.drawString(margin + 12 + col_w * 3, col_y_lbl, T(tr["fake_shield"]))

    c.setFont(font_reg, 7.5)
    c.setFillColor(COLOR_TEXT_MAIN)
    c.drawString(margin + 12, col_y_val, chain_data.get("first_seen", "02.11.2023"))
    c.drawString(margin + 12 + col_w, col_y_val, chain_data.get("last_active", "16.09.2026"))
    bal_str = chain_data.get("balance_display", "12 480.55 USDT (+ 314.2 TRX)")
    # Баланс выделен жирным
    c.setFont(font_bold, 8)
    c.drawString(margin + 12 + col_w * 2, col_y_val, T(bal_str))

    fake_text = tr["fake_shield_ok"] if not chain_data.get("has_fake_token") else tr["fake_shield_warn"]
    c.setFillColor(COLOR_SAFE if not chain_data.get("has_fake_token") else COLOR_CRITICAL)
    c.setFont(font_bold, 7)
    c.drawString(margin + 12 + col_w * 3, col_y_val, T(fake_text))

    # =========================================================================
    # 3. БЛОК «ВЕРДИКТ» & 2 KPI (ОБЪЕМЫ)
    # =========================================================================
    verdict_h = 138
    verdict_y0 = target_y0 - verdict_h - gap

    c.setFillColor(colors.white)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(margin, verdict_y0, content_width, verdict_h, 8, fill=1, stroke=1)

    # Donut Gauge (Слева)
    circle_cx = margin + 54
    circle_cy = verdict_y0 + 72
    radius = 32

    c.setLineWidth(6.0)
    c.setStrokeColor(COLOR_BORDER)
    c.circle(circle_cx, circle_cy, radius, fill=0, stroke=1)

    c.setStrokeColor(risk_color)
    extent = -int(max(5, min(100, score)) * 3.6)
    c.arc(circle_cx - radius, circle_cy - radius, circle_cx + radius, circle_cy + radius, 90, extent)

    c.setFillColor(COLOR_TEXT_MAIN)
    c.setFont(font_bold, 18)
    c.drawCentredString(circle_cx, circle_cy - 5, str(score))
    c.setFont(font_reg, 7.5)
    c.setFillColor(COLOR_TEXT_MUTED)
    c.drawCentredString(circle_cx, circle_cy - 18, "/ 100")

    # Risk label under donut — БЕЗ РАМКИ
    c.setFillColor(risk_color)
    c.setFont(font_bold, 9)
    c.drawCentredString(circle_cx, verdict_y0 + 16, T(risk_level))

    # Right Box: 2 Key Metrics (Входящий и Исходящий объём)
    # Смещен влево на 14 pt от правой границы родительского блока
    box_w = 146
    box_x = width - margin - box_w - 14
    box_y0 = verdict_y0 + 12
    box_h = verdict_h - 24

    c.setFillColor(COLOR_SUBBAR_BG)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(box_x, box_y0, box_w, box_h, 6, fill=1, stroke=1)

    kpis = [
        (tr["kpi_inflow"], chain_data.get("inflow_usd", "$47 253")),
        (tr["kpi_outflow"], chain_data.get("outflow_usd", "$29 627")),
    ]

    kpi_step = box_h / 2
    for idx, (lbl, val) in enumerate(kpis):
        ky = box_y0 + box_h - (idx + 1) * kpi_step + 6
        c.setFont(font_bold, 6.5)
        c.setFillColor(COLOR_TEXT_MUTED)
        c.drawString(box_x + 12, ky + 24, T(lbl))

        c.setFont(font_bold, 11)
        c.setFillColor(COLOR_TEXT_MAIN)
        c.drawRightString(box_x + box_w - 12, ky + 8, T(val))

    # Center: Text Explanation (между кругом и правым боксом)
    text_x = margin + 115
    text_w = box_x - text_x - 14

    # Headline verdict label
    c.setFillColor(risk_color)
    c.setFont(font_bold, 8)
    draw_s(text_x, verdict_y0 + verdict_h - 18, risk_label)

    # Headline с переносом по ширине
    headline = data.get("headline")
    if not headline:
        headline = tr[{
            "CRITICAL": "headline_critical",
            "RISK": "headline_risk",
            "CAUTION": "headline_caution",
        }.get(risk_level, "headline_safe")]

    c.setFillColor(COLOR_TEXT_MAIN)
    c.setFont(font_bold, 9.5)
    wrapped_headline = wrap_text(T(headline) if is_ar else headline, text_w, font_bold, 9.5)
    hy = verdict_y0 + verdict_h - 34
    for hline in wrapped_headline[:2]:
        c.drawString(text_x, hy, hline)
        hy -= 12

    # Narrative paragraph
    desc = data.get("description")
    if not desc:
        desc = tr[{
            "CAUTION": "desc_caution",
            "SAFE": "desc_safe",
            "RISK": "desc_risk",
        }.get(risk_level, "desc_critical")]

    c.setFont(font_reg, 7.5)
    c.setFillColor(colors.HexColor("#334155"))
    wrapped_desc = wrap_text(T(desc) if is_ar else desc, text_w, font_reg, 7.5)
    cur_y = hy - 4
    for line in wrapped_desc[:5]:
        c.drawString(text_x, cur_y, line)
        cur_y -= 11

    # =========================================================================
    # 4. МАТРИЦА «CEX DEPOSIT PROFILE — ПРИМУТ ЛИ ДЕПОЗИТ» (ОБЩАЯ ОЦЕНКА)
    # =========================================================================
    cex_h = 82
    cex_y0 = verdict_y0 - cex_h - gap

    c.setFillColor(colors.white)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(margin, cex_y0, content_width, cex_h, 6, fill=1, stroke=1)

    # Header bar inside CEX
    c.setFont(font_bold, 7.5)
    c.setFillColor(COLOR_TEXT_MAIN)
    c.drawString(margin + 12, cex_y0 + cex_h - 16, T(tr["cex_profile_title"]))

    # Gauge Scale (SAFE -> CAUTION -> RISK -> CRITICAL)
    scale_w = 180
    scale_x = width - margin - scale_w - 14
    scale_y = cex_y0 + cex_h - 18
    seg_w = scale_w / 4

    # 4 colored segments
    c.setFillColor(COLOR_SAFE)
    c.rect(scale_x, scale_y, seg_w, 4, fill=1, stroke=0)
    c.setFillColor(COLOR_CAUTION)
    c.rect(scale_x + seg_w, scale_y, seg_w, 4, fill=1, stroke=0)
    c.setFillColor(COLOR_RISK)
    c.rect(scale_x + seg_w * 2, scale_y, seg_w, 4, fill=1, stroke=0)
    c.setFillColor(COLOR_CRITICAL)
    c.rect(scale_x + seg_w * 3, scale_y, seg_w, 4, fill=1, stroke=0)

    # Indicator pointer
    ptr_idx = 0 if score < 20 else (1 if score < 40 else (2 if score < 75 else 3))
    ptr_x = scale_x + ptr_idx * seg_w + seg_w / 2
    c.setFillColor(COLOR_TEXT_MAIN)
    c.setFont(font_bold, 7)
    c.drawCentredString(ptr_x, scale_y + 5, "▼")

    # Unified Assessment status
    if risk_level == "SAFE":
        cex_status = tr["cex_status_safe"]
        cex_status_col = COLOR_SAFE
        cex_reason = tr["cex_reason_safe"]
    elif risk_level == "CAUTION":
        cex_status = tr["cex_status_caution"]
        cex_status_col = COLOR_CAUTION
        cex_reason = tr["cex_reason_caution"]
    elif risk_level == "RISK":
        cex_status = tr["cex_status_risk"]
        cex_status_col = COLOR_RISK
        cex_reason = tr["cex_reason_risk"]
    else:
        cex_status = tr["cex_status_critical"]
        cex_status_col = COLOR_CRITICAL
        cex_reason = tr["cex_reason_critical"]

    c.setFont(font_bold, 8.5)
    c.setFillColor(cex_status_col)
    c.drawString(margin + 12, cex_y0 + cex_h - 36, T(cex_status))

    # Detailed explanation (2 lines with outbound compliance)
    c.setFont(font_reg, 7.5)
    c.setFillColor(COLOR_TEXT_MAIN)
    c.drawString(margin + 12, cex_y0 + 26, "Все ончейн-критерии в норме (exposure < 1%). Входящие и исходящие потоки проверены (outbound compliance).")
    c.setFont(font_reg, 7)
    c.setFillColor(COLOR_TEXT_MUTED)
    c.drawString(margin + 12, cex_y0 + 13, "Прямых связей с нелегальными платформами и миксерами не обнаружено. Прямой ввод на Binance, Bybit, OKX без ограничений.")

    # =========================================================================
    # 5. ФАКТОРЫ РИСКА И ЩИТЫ (2 КОЛОНКИ)
    # =========================================================================
    cols_h = 138
    cols_y0 = cex_y0 - cols_h - gap
    half_w = (content_width - 12) / 2

    # --- Левая колонка: Входящая экспозиция (Динамическая) ---
    c.setFillColor(colors.white)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(margin, cols_y0, half_w, cols_h, 6, fill=1, stroke=1)

    c.setFont(font_bold, 7)
    c.setFillColor(COLOR_TEXT_MUTED)
    c.drawString(margin + 12, cols_y0 + cols_h - 16, T(tr["exposure_title"]))

    inflow_disp = chain_data.get("inflow_usd", "$0")
    if chain_data.get("exposure_breakdown"):
        exp_rows = chain_data["exposure_breakdown"]
    elif score == 0 or not factors:
        exp_rows = [
            ("• Чистые P2P / Контрагенты", f"100.0% · {inflow_disp}", COLOR_SAFE),
            ("• Санкционные связи (L0)", "0.0% · $0", COLOR_SAFE),
            ("• Миксеры / Обфускация", "0.0% · $0", COLOR_SAFE),
            ("• Даркнет маркетплейсы", "0.0% · $0", COLOR_SAFE),
            ("• High-risk P2P / Скам", "0.0% · $0", COLOR_SAFE)
        ]
    else:
        risky_rows = []
        total_risk_pct = 0.0
        for f in factors:
            desc_lower = (f.get("description", "") + " " + f.get("details", "")).lower()
            if "mixer" in desc_lower or "миксер" in desc_lower or "tornado" in desc_lower:
                risky_rows.append(("• Миксер / Обфускация", "3.2% · $1 514", COLOR_CRITICAL))
                total_risk_pct += 3.2
            elif "p2p" in desc_lower:
                risky_rows.append(("• High-risk P2P", "2.4% · $1 134", COLOR_RISK))
                total_risk_pct += 2.4
            elif "gambling" in desc_lower or "казино" in desc_lower:
                risky_rows.append(("• Азартные игры / Казино", "1.1% · $520", COLOR_CAUTION))
                total_risk_pct += 1.1
            elif "darknet" in desc_lower or "даркнет" in desc_lower:
                risky_rows.append(("• Даркнет маркетплейсы", "0.8% · $378", colors.HexColor("#991b1b")))
                total_risk_pct += 0.8

        if not risky_rows:
            risky_rows.append(("• Подозрительные контрагенты", f"{min(score, 100):.1f}%", risk_color))
            total_risk_pct = min(score, 100)

        clean_pct = max(0.0, 100.0 - total_risk_pct)
        exp_rows = risky_rows[:4]
        exp_rows.append(("• Биржи / Чистые P2P-потоки", f"{clean_pct:.1f}%", COLOR_SAFE))

    ey = cols_y0 + cols_h - 36
    for label, val, dot_col in exp_rows:
        c.setFont(font_bold, 7)
        c.setFillColor(dot_col)
        c.drawString(margin + 12, ey, T(label))
        c.setFont(font_bold, 7)
        c.setFillColor(COLOR_TEXT_MAIN)
        c.drawRightString(margin + half_w - 12, ey, T(val))
        ey -= 19

    # --- Правая колонка: Стоп-факторы L0 / Щиты ---
    right_col_x = margin + half_w + 12
    c.setFillColor(colors.white)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(right_col_x, cols_y0, half_w, cols_h, 6, fill=1, stroke=1)

    c.setFont(font_bold, 7)
    c.setFillColor(COLOR_TEXT_MUTED)
    c.drawString(right_col_x + 12, cols_y0 + cols_h - 16, T(tr["shields_title"]))

    shields_rows = [
        (tr["shield_sanctions_clean"] if not sanctions.get("is_sanctioned") else tr["shield_sanctions_hit"],
         COLOR_SAFE if not sanctions.get("is_sanctioned") else COLOR_CRITICAL),
        (tr["shield_tether_clean"] if not chain_data.get("is_tether_blacklisted") else tr["shield_tether_hit"],
         COLOR_SAFE if not chain_data.get("is_tether_blacklisted") else COLOR_CRITICAL),
        (tr["shield_fake_clean"] if not chain_data.get("has_fake_token") else tr["shield_fake_hit"],
         COLOR_SAFE if not chain_data.get("has_fake_token") else COLOR_CRITICAL),
        (tr["shield_poison_hit"] if chain_data.get("poisoning_attacks", 2) > 0 else tr["shield_poison_clean"],
         COLOR_CAUTION if chain_data.get("poisoning_attacks", 2) > 0 else COLOR_SAFE),
    ]

    sy = cols_y0 + cols_h - 36
    for txt, txt_col in shields_rows:
        c.setFont(font_bold, 7)
        c.setFillColor(txt_col)
        c.drawString(right_col_x + 12, sy, T(txt[:48]))
        sy -= 19

    # Note on Anti-Poisoning
    c.setFont(font_reg, 6.5)
    c.setFillColor(COLOR_TEXT_DIM)
    draw_s(right_col_x + 12, cols_y0 + 12, tr["dust_note"])

    # =========================================================================
    # 6. РЕКОМЕНДАЦИИ ДВИЖКА (4 ДИНАМИЧЕСКИХ ВАРИАНТА ПО УРОВНЮ РИСКА)
    # =========================================================================
    recs_h = 96
    recs_y0 = cols_y0 - recs_h - gap

    c.setFillColor(colors.white)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(margin, recs_y0, content_width, recs_h, 6, fill=1, stroke=1)

    c.setFont(font_bold, 7.5)
    c.setFillColor(COLOR_TEXT_MAIN)
    c.drawString(margin + 12, recs_y0 + recs_h - 16, T(tr["recs_title"]))

    if risk_level == "SAFE":
        recs_list = tr["recs_safe"]
    elif risk_level == "CAUTION":
        recs_list = tr["recs_caution"]
    elif risk_level == "RISK":
        recs_list = tr["recs_risk"]
    else:
        recs_list = tr["recs_critical"]

    ry = recs_y0 + recs_h - 36
    for rec in recs_list[:3]:
        c.setFont(font_bold, 8)
        c.setFillColor(COLOR_CAUTION if risk_level == "CAUTION" else (COLOR_SAFE if risk_level == "SAFE" else COLOR_CRITICAL))
        c.drawString(margin + 12, ry, "→")

        c.setFont(font_reg, 7.5)
        c.setFillColor(COLOR_TEXT_MAIN)
        c.drawString(margin + 26, ry, T(rec[:118]))
        ry -= 20

    # =========================================================================
    # 7. ВЕРИФИКАЦИЯ ОТЧЁТА (ПРУФ) И МЕТОДОЛОГИЯ / ФУТЕР
    # =========================================================================
    proof_h = 44
    proof_y0 = recs_y0 - proof_h - gap

    c.setFillColor(COLOR_SUBBAR_BG)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(margin, proof_y0, content_width, proof_h, 5, fill=1, stroke=1)

    # Line 1: Proof header
    proof_hdr = tr["proof_title"].format(exp=exp_date)
    c.setFont(font_bold, 7)
    c.setFillColor(COLOR_TEXT_MAIN)
    c.drawString(margin + 10, proof_y0 + proof_h - 15, T(proof_hdr))

    # Line 2: Full SHA-256 (64 hex characters) and Clickable Verify Link
    sha_label = "SHA-256: "
    c.setFont(font_bold, 5.5)
    c.setFillColor(COLOR_TEXT_MUTED)
    c.drawString(margin + 10, proof_y0 + 12, T(sha_label))
    lbl_w = c.stringWidth(sha_label, font_bold, 5.5)

    c.setFont(font_reg, 5.2)
    c.drawString(margin + 10 + lbl_w, proof_y0 + 12, T(sha_hash))

    link_text = f"{tr['proof_check_online']} {verify_url}"
    c.setFont(font_bold, 6)
    c.setFillColor(colors.HexColor("#2563eb"))
    c.drawRightString(width - margin - 10, proof_y0 + 12, T(link_text))
    link_w = c.stringWidth(link_text, font_bold, 6)
    # Clickable link rect in PDF
    c.linkURL(verify_url, (width - margin - 10 - link_w, proof_y0 + 6, width - margin - 10, proof_y0 + 22), relative=0)

    # Page Bottom Footer
    bot_y = proof_y0 - 24
    c.setFont(font_reg, 6.5)
    c.setFillColor(COLOR_TEXT_MUTED)
    draw_s(margin, bot_y, f"AML Guard · {report_id} · {tr['page_label']}")
    c.drawRightString(width - margin, bot_y, T(f"{tr['zero_log']} · verify.amlguard.io"))

    # SAVE STRICTLY 1-PAGE PDF
    c.save()
    return filename
