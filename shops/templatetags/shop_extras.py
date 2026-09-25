from django import template

register = template.Library()

LEBANON_COUNTRY_CODE = "961"


@register.filter
def format_whatsapp(number):
    """Formats a stored WhatsApp number (digits only, e.g. "96170123456")
    for display, dropping the Lebanese country code and grouping the
    local number as 2-3-3 (e.g. "70 123 456"). Falls back to the raw
    digits if the number doesn't match that shape (blank, no country
    code, or an unexpected length)."""
    if not number:
        return ""

    local_number = number
    if local_number.startswith(LEBANON_COUNTRY_CODE):
        local_number = local_number[len(LEBANON_COUNTRY_CODE):]

    if len(local_number) == 8:
        return f"{local_number[0:2]} {local_number[2:5]} {local_number[5:8]}"

    return local_number
