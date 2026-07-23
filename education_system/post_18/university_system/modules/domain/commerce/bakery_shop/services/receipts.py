"""ReceiptsMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class ReceiptsMixin:
    def _make_qr_png(self, payload, *, path):
        try:
            import qrcode  # type: ignore
            img = qrcode.make(payload)
            img.save(path)
            return path
        except Exception:
            logger.debug("QR generation failed for payload=%r",
                         payload, exc_info=True)
            return None

    def export_receipt_pdf(self, order, *, out_path=None):
        """Generate a print-friendly PDF receipt for an order, including
        a QR code that encodes the order ID for refund/lookup."""
        try:
            try:
                from reportlab.lib.pagesizes import A5
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                                  Spacer, Table, TableStyle,
                                                  Image)
                from reportlab.lib import colors as rl_colors
            except Exception:
                logger.warning("reportlab not installed; cannot make PDF receipt")
                return None
            if not out_path:
                out_path = os.path.join(
                    self._exports_dir(),
                    f"receipt_{order['order_id']}_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            doc = SimpleDocTemplate(out_path, pagesize=A5)
            styles = getSampleStyleSheet()
            story = [
                Paragraph("🥐 University Bakery Shop", styles["Title"]),
                Paragraph(f"Receipt — {order['order_id']}", styles["Heading3"]),
                Paragraph(f"Date: {order.get('timestamp', '')}",
                          styles["Normal"]),
                Paragraph(f"Customer: {order.get('user', '')}",
                          styles["Normal"]),
                Spacer(1, 10),
            ]
            rows = [["Item", "Qty", "Price (£)"]]
            for name, qty in (order.get("items") or {}).items():
                info = self._product_info(name)
                price = float(info["price"]) if info else 0.0
                rows.append([name, qty, f"{price * qty:.2f}"])
            story.append(Table(rows, style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.25, rl_colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), rl_colors.lightgrey),
            ])))
            story.append(Spacer(1, 10))
            totals = [
                ["Subtotal",        f"£{order.get('subtotal', 0):.2f}"],
                ["Discount",        f"£{order.get('discount', 0):.2f}"],
                ["of which VAT",    f"£{order.get('vat_amount', 0) or 0:.2f}"],
                ["Tip",             f"£{order.get('tip_amount', 0) or 0:.2f}"],
                ["TOTAL PAID",      f"£{order.get('total', 0):.2f}"],
                ["Payment",         (order.get('payment_method') or 'cash')
                                      .replace('_', ' ').title()],
            ]
            story.append(Table(totals, style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.25, rl_colors.grey),
                ("BACKGROUND", (0, -2), (-1, -2), rl_colors.lightgrey),
                ("FONTNAME", (0, -2), (-1, -2), "Helvetica-Bold"),
            ])))
            story.append(Spacer(1, 10))
            # QR code with order ID payload
            qr_path = self._make_qr_png(
                f"BAKERY|{order['order_id']}|{order.get('total', 0):.2f}",
                path=os.path.join(self._exports_dir(),
                                  f"qr_{order['order_id']}.png"))
            if qr_path and os.path.isfile(qr_path):
                story.append(Image(qr_path, width=80, height=80))
                story.append(Paragraph(
                    "Scan to look up this order / start a refund request.",
                    styles["Italic"]))
            doc.build(story)
            logger.info("Receipt PDF exported order=%s -> %s",
                        order["order_id"], out_path)
            return out_path
        except Exception:
            logger.exception("export_receipt_pdf failed order=%s",
                             order.get("order_id"))
            return None

    def _print_receipt_for_selected(self):
        sel = self.orders_tree.selection() if hasattr(self, "orders_tree") else None
        if not sel:
            messagebox.showinfo("Select an order",
                                "Select an order to print.")
            return
        order_id = self.orders_tree.item(sel[0])["values"][0]
        order = next((o for o in self.orders if o["order_id"] == order_id), None)
        if not order:
            return
        path = self.export_receipt_pdf(order)
        if path:
            messagebox.showinfo("Receipt saved", f"Receipt written to:\n{path}")
        else:
            messagebox.showerror("Error",
                                  "Could not generate receipt (is reportlab "
                                  "and qrcode installed?).")

