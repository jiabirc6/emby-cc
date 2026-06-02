"""Telegram checkin plugin registry"""

from emby_cc.plugins.telegram.base import TelegramBotCheckin
from emby_cc.plugins.telegram.templ_a import TemplateACheckin
from emby_cc.plugins.telegram.templ_b import TemplateBCheckin
from emby_cc.plugins.telegram.meow import MeowCheckin

PLUGIN_REGISTRY = {"meow": MeowCheckin}

_TEMPLATE_A = [
    ("youno", "YounoEmbyAgain_bot"),
    ("yezi", "yeziemby_bot"),
    ("okemby", "okemby_bot"),
    ("hgemby", "HG_Emby_bot"),
    ("syembyy", "syembyy_bot"),
    ("youqibing", "youqibing_bot"),
    ("lz_cookie", "lz_cookie_bot"),
    ("totoro_emby", "totoro_emby_bot"),
    ("peach_emby", "peach_emby_bot"),
    ("sadchick", "sadchick_bot"),
    ("xyz_gy", "xyz_gy_bot"),
    ("xgfree", "XGFree_bot"),
    ("jerryporn", "jerryporn_bot"),
    ("miraiemby", "miraiemby_bot"),
    ("fyemby", "fyemby_bot"),
    ("cinetrail", "Cinetrail_bot"),
    ("fortesttlbot", "fortesttlbot_bot"),
]

_TEMPLATE_B = [
    ("emospg", "emospg_bot"),
]

for name, bot in _TEMPLATE_A:
    PLUGIN_REGISTRY[name] = type(f"TA_{name}", (TemplateACheckin,), {"name": name, "bot_username": bot})

for name, bot in _TEMPLATE_B:
    PLUGIN_REGISTRY[name] = type(f"TB_{name}", (TemplateBCheckin,), {"name": name, "bot_username": bot})

__all__ = ["TelegramBotCheckin", "TemplateACheckin", "TemplateBCheckin", "MeowCheckin", "PLUGIN_REGISTRY"]
