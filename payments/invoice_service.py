from io import BytesIO
from xml.sax.saxutils import escape

from django.db import transaction
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from orders.models import Order

from .models import Invoice


def _text(value):
    return escape(str(value or ""))


@transaction.atomic
def get_or_create_invoice(order):
    locked_order = (
        Order.objects
        .select_for_update(of=("self",))
        .select_related(
            "shop",
            "selected_payment_method",
            "payment",
        )
        .prefetch_related("items")
        .get(pk=order.pk)
    )

    invoice, _ = Invoice.objects.get_or_create(
        order=locked_order,
        defaults={
            "shop": locked_order.shop,
            "invoice_number": (
                f"INV-{locked_order.shop_id}-{locked_order.pk}"
            ),
            "issued_at": timezone.now(),
            "subtotal_snapshot": locked_order.items_total,
            "delivery_fee_snapshot": (
                locked_order.delivery_fee_snapshot
            ),
            "total_snapshot": locked_order.total,
            "currency": locked_order.currency,
            "status": Invoice.Status.ISSUED,
        },
    )

    return invoice, locked_order


def build_invoice_pdf(invoice, order):
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author="Ordira",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#554CFF"),
        spaceAfter=8,
    )
    heading_style = ParagraphStyle(
        "InvoiceHeading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#27272A"),
        spaceBefore=10,
        spaceAfter=7,
    )
    body_style = ParagraphStyle(
        "InvoiceBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#3F3F46"),
    )
    small_style = ParagraphStyle(
        "InvoiceSmall",
        parent=body_style,
        fontSize=8,
        leading=11,
    )
    right_style = ParagraphStyle(
        "InvoiceRight",
        parent=body_style,
        alignment=TA_RIGHT,
    )
    header_cell_style = ParagraphStyle(
        "InvoiceHeaderCell",
        parent=small_style,
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    story = [
        Paragraph(_text(order.shop.name), title_style),
        Paragraph(
            f"WhatsApp: {_text(order.shop.whatsapp or 'Not available')}",
            body_style,
        ),
        Spacer(1, 8),
    ]

    issued_at = invoice.issued_at or timezone.now()

    invoice_information = Table(
        [
            [
                Paragraph("<b>Invoice number</b>", body_style),
                Paragraph(_text(invoice.invoice_number), right_style),
            ],
            [
                Paragraph("<b>Order number</b>", body_style),
                Paragraph(_text(order.order_number), right_style),
            ],
            [
                Paragraph("<b>Order date</b>", body_style),
                Paragraph(
                    timezone.localtime(order.created_at).strftime(
                        "%b %d, %Y %H:%M"
                    ),
                    right_style,
                ),
            ],
            [
                Paragraph("<b>Invoice date</b>", body_style),
                Paragraph(
                    timezone.localtime(issued_at).strftime(
                        "%b %d, %Y %H:%M"
                    ),
                    right_style,
                ),
            ],
        ],
        colWidths=[60 * mm, 98 * mm],
    )
    invoice_information.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F7FF")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDF0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E4E4E7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([invoice_information, Spacer(1, 12)])

    story.append(Paragraph("Customer and fulfillment", heading_style))

    fulfillment_lines = [
        f"<b>Customer:</b> {_text(order.customer_name_snapshot)}",
        f"<b>Phone:</b> {_text(order.customer_phone_snapshot)}",
        (
            f"<b>Fulfillment:</b> "
            f"{_text(order.get_fulfillment_type_display())}"
        ),
    ]

    if order.fulfillment_type == Order.FulfillmentType.DELIVERY:
        fulfillment_lines.extend(
            [
                f"<b>Delivery zone:</b> {_text(order.zone_name_snapshot)}",
                f"<b>Address:</b> {_text(order.address_snapshot)}",
            ]
        )

    for line in fulfillment_lines:
        story.append(Paragraph(line, body_style))

    story.extend(
        [
            Spacer(1, 10),
            Paragraph("Order items", heading_style),
        ]
    )

    item_rows = [
        [
            Paragraph("Product", header_cell_style),
            Paragraph("Color", header_cell_style),
            Paragraph("Size", header_cell_style),
            Paragraph("Unit price", header_cell_style),
            Paragraph("Qty", header_cell_style),
            Paragraph("Line total", header_cell_style),
        ]
    ]

    for item in order.items.all():
        item_rows.append(
            [
                Paragraph(
                    _text(item.product_name_snapshot),
                    small_style,
                ),
                Paragraph(_text(item.color_snapshot), small_style),
                Paragraph(_text(item.size_snapshot), small_style),
                Paragraph(
                    f"{item.unit_price_snapshot:.2f}",
                    right_style,
                ),
                Paragraph(str(item.quantity), right_style),
                Paragraph(
                    f"{item.line_total:.2f}",
                    right_style,
                ),
            ]
        )

    items_table = LongTable(
        item_rows,
        repeatRows=1,
        colWidths=[
            55 * mm,
            23 * mm,
            18 * mm,
            24 * mm,
            13 * mm,
            27 * mm,
        ],
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#554CFF")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D4D4D8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, -1),
                    colors.white,
                ),
            ]
        )
    )
    story.extend([items_table, Spacer(1, 12)])

    totals_table = Table(
        [
            [
                Paragraph("Subtotal", body_style),
                Paragraph(
                    (
                        f"{invoice.subtotal_snapshot:.2f} "
                        f"{invoice.currency}"
                    ),
                    right_style,
                ),
            ],
            [
                Paragraph("Delivery fee", body_style),
                Paragraph(
                    (
                        f"{invoice.delivery_fee_snapshot:.2f} "
                        f"{invoice.currency}"
                    ),
                    right_style,
                ),
            ],
            [
                Paragraph("<b>Total</b>", body_style),
                Paragraph(
                    (
                        f"<b>{invoice.total_snapshot:.2f} "
                        f"{invoice.currency}</b>"
                    ),
                    right_style,
                ),
            ],
        ],
        colWidths=[90 * mm, 68 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#554CFF")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([totals_table, Spacer(1, 12)])

    payment = getattr(order, "payment", None)

    if payment is not None:
        payment_method = payment.method_name_snapshot
        payment_status = payment.get_status_display()
    else:
        payment_method = (
            order.selected_payment_method.get_method_name_display()
        )
        payment_status = "Not recorded"

    story.extend(
        [
            Paragraph("Payment", heading_style),
            Paragraph(
                f"<b>Selected method:</b> {_text(payment_method)}",
                body_style,
            ),
            Paragraph(
                f"<b>Payment status:</b> {_text(payment_status)}",
                body_style,
            ),
        ]
    )

    document.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes